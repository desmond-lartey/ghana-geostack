"""Every host the viewer fetches from must be allowed to be fetched from.

This exists because of one bug that cost an afternoon and looked like
something else entirely. ``gibs.earthdata.nasa.gov`` was in the policy's
``img-src`` and not in its ``connect-src``. That reads as correct — tiles are
images — but MapLibre GL does not load raster tiles with an ``<img>`` tag. It
fetches them, so ``connect-src`` is the directive that governs, and every NASA
tile was refused before it left the browser.

What made it expensive is how it failed. The layer registered, the layer card
appeared, the legend listed it, the log said the layer had been added, and the
map stayed empty. Nothing anywhere said "refused", because the refusal was in
the console and the application never looked there.

So: any tile template or fetch target written into the page must appear in
both directives. A host added to one and not the other fails here rather than
in front of someone.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "web/index.html"
VERCEL = ROOT / "vercel.json"

# Hosts reached by something other than fetch, or not reached at all: a link
# for a person to click, documentation, a sign-in page opened in a popup.
NOT_FETCHED = {
    "https://carto.com",
    "https://console.cloud.google.com",
    "https://github.com",
    "https://opentopomap.org",
    "https://www.openstreetmap.org",
    "https://desmond-lartey.github.io",
    "https://fonts.googleapis.com",     # style-src
    "https://fonts.gstatic.com",        # font-src
    "https://ajax.googleapis.com",      # script-src
    "https://accounts.google.com",      # frame-src and connect-src both
    "https://openrouter.ai",            # a model endpoint the reader may type
}


def directives():
    policy = None
    for header in json.loads(VERCEL.read_text()).get("headers", []):
        for entry in header.get("headers", []):
            if "Content-Security-Policy" in entry["key"]:
                policy = entry["value"]
    assert policy, "no Content-Security-Policy in vercel.json"
    out = {}
    for part in policy.split(";"):
        bits = part.split()
        if bits:
            out[bits[0]] = set(bits[1:])
    return out


def allowed(host, sources):
    """A host is allowed by an exact entry or by a wildcard that covers it."""
    if host in sources:
        return True
    name = host.removeprefix("https://")
    for src in sources:
        if src.startswith("https://*."):
            suffix = src.removeprefix("https://*.")
            if name == suffix or name.endswith("." + suffix):
                return True
    return False


def page_hosts():
    text = PAGE.read_text()
    found = set(re.findall(r"https://[a-z0-9.*-]+\.[a-z]{2,}", text))
    return {h for h in found if h not in NOT_FETCHED}


def test_every_fetched_host_is_in_connect_src():
    rules = directives()
    missing = sorted(h for h in page_hosts() if not allowed(h, rules["connect-src"]))
    assert not missing, (
        "the page fetches from hosts the policy refuses to connect to, so they "
        "fail silently and the map just stays empty: " + ", ".join(missing))


def test_tile_hosts_are_in_both_directives():
    """A tile host must satisfy img-src and connect-src.

    Which of the two MapLibre uses depends on the browser and the version, so
    a host in only one of them works in some browsers and not others, which is
    worse than failing everywhere.
    """
    rules = directives()
    tiles = {h for h in page_hosts()
             if re.search(r"tile|basemaps|arcgisonline|gibs|elevation", h)}
    assert tiles, "no tile hosts found in the page, which cannot be right"
    bad = []
    for host in sorted(tiles):
        for directive in ("img-src", "connect-src"):
            if not allowed(host, rules[directive]):
                bad.append(f"{host} is not in {directive}")
    assert not bad, "; ".join(bad)
