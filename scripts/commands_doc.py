"""Write the command reference from the registry itself.

The ribbon's commands live in one place in `web/index.html`; this reads them
and writes `docs/commands.md`. A hand-kept list of 168 commands is a list that
is wrong within a month, and the whole point of the page is to tell a
contributor which slots are open — so it has to be true.

Usage:
    python scripts/commands_doc.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web" / "index.html"
OUT = ROOT / "docs" / "commands.md"


def registry(text: str) -> dict[str, dict]:
    """Every command, and whether it has a `run`."""
    start = text.index("const COMMANDS = {")
    end = text.index("\n};", start)
    body = text[start:end]

    out: dict[str, dict] = {}
    for block in re.finditer(
        r'\n  "([^"]+)": \{\n(.*?)\n  \}', body, re.S
    ):
        cid, fields = block.group(1), block.group(2)
        label = re.search(r'label: "((?:[^"\\]|\\.)*)"', fields)
        desc = re.search(r'desc: "((?:[^"\\]|\\.)*)"', fields)
        out[cid] = {
            "label": json.loads(f'"{label.group(1)}"') if label else cid,
            "desc": json.loads(f'"{desc.group(1)}"') if desc else "",
            "built": "run:" in fields,
        }
    return out


def spec(text: str) -> list[tuple[str, str, list[str]]]:
    """(tab, group, [command ids]) in the order the ribbon draws them."""
    start = text.index("const RIBBON = [")
    end = text.index("\n];", start)
    body = text[start:end]

    out = []
    for tab_match in re.finditer(r'\{ tab: "([^"]+)", groups: \[(.*?)\n  \] \}', body, re.S):
        tab = tab_match.group(1)
        for group in re.finditer(r'\{ group: "([^"]+)", controls: \[(.*?)\] \}', tab_match.group(2)):
            ids = re.findall(r'cmd: "([^"]+)"', group.group(2))
            out.append((tab, group.group(1), ids))
    return out


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    commands = registry(text)
    layout = spec(text)

    built = sum(1 for c in commands.values() if c["built"])
    open_slots = len(commands) - built

    lines = [
        "# Command reference",
        "",
        "Every control on the ribbon runs one command by id, and this is the list.",
        "It is generated from the registry in `web/index.html` by",
        "`python scripts/commands_doc.py`, so it cannot drift from what the",
        "interface actually does.",
        "",
        f"**{len(commands)} commands. {built} are built. {open_slots} are open.**",
        "",
        "An open slot is not a bug. The ribbon, the registry and the place each",
        "command plugs into are finished; the function behind it is the work, and",
        "it is deliberately left for the people who will use this platform. Each",
        "one is a small, self-contained job: add a `run` to its entry in the",
        "`COMMANDS` registry and the button, its icon, its tooltip and its place",
        "on the tab are already there.",
        "",
        "In the interface, an open slot carries a gold dot and pressing it says",
        "what it is for and what it is called. **Ctrl K** searches every command",
        "by name.",
        "",
        "---",
        "",
    ]

    for tab in dict.fromkeys(t for t, _, _ in layout):
        lines += [f"## {tab}", ""]
        for t, group, ids in layout:
            if t != tab:
                continue
            lines += [f"### {group}", "",
                      "| Command | Does | Status |",
                      "| --- | --- | --- |"]
            for cid in ids:
                c = commands.get(cid)
                if not c:
                    continue
                state = "Built" if c["built"] else "**Open**"
                lines.append(f"| `{cid}` | {c['desc']} | {state} |")
            lines.append("")

    orphans = [cid for cid in commands
               if not any(cid in ids for _, _, ids in layout)]
    if orphans:
        lines += ["## Not on a tab", "",
                  "Commands the registry holds that no ribbon control names. They run",
                  "from command search and from the assistant.", "",
                  "| Command | Does | Status |", "| --- | --- | --- |"]
        for cid in orphans:
            c = commands[cid]
            lines.append(f"| `{cid}` | {c['desc']} | "
                         f"{'Built' if c['built'] else '**Open**'} |")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {OUT.relative_to(ROOT)} — {len(commands)} commands, "
          f"{built} built, {open_slots} open")


if __name__ == "__main__":
    main()
