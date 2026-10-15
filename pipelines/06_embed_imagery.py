#!/usr/bin/env python3
"""Turn imagery into the vectors the viewer searches, after DinoSats.

    python pipelines/06_embed_imagery.py --image accra.tif --out public/scenes/accra

What this makes is a *scene*: three static files the viewer loads over HTTP.

    scene.json      the manifest — size, bounds, how to dequantise
    scene.u8        width x height x dim uint8, the patch vectors
    prompts.json    a table of precomputed text vectors

Why three files and not one. The vectors are the big one and they never
change; the prompts are small and get added to as people find words that
work. Splitting them means a new prompt costs a few kilobytes rather than a
re-download of the scene.

WHAT THIS NEEDS, and it is not little:

  * a CUDA GPU with 16 GB or more
  * the gated DINOv3 weights from Hugging Face, which need an account and an
    accepted licence
  * the dino.txt text head, for turning words into vectors of the same kind
  * imagery at a metre or better. Sentinel-2 at 10 m does not work for this:
    DINOv3 was trained on photographs, and a 10 m patch of Accra is not
    recognisable as anything to a model that has seen photographs.

So this is not something that runs in CI, and it is not something the viewer
can do for itself. It is a few hours of GPU time per city, once, and then
every search over that city is instant and free for everyone.

HOW IT SCORES, so the numbers in the browser can be checked against this:

    cos(prompt, patch) for every patch, then
    score = sigmoid(s * cos_query - logsumexp(s * cos_background))

The background correction is the difference between a heatmap and a mess.
A raw cosine has no meaningful zero; the corrected score asks whether a patch
matches your words better than it matches "water", "road" and "trees", which
is the question anyone actually has.

WHAT IT IS GOOD AT, from the DinoSats write-up and worth repeating because it
sets expectations:

  * Large distinctive things seen from above: runways, quarries, sports
    fields, large rooftops, water. In Ghana: the Akosombo dam, Tema harbour,
    the Obuasi workings, irrigated blocks at Kpong.
  * Word choice matters more than it should. "rooftops" beats "buildings"
    and "houses" by a wide margin, for no reason anyone can state in advance.
    Try several.
  * It is zero-shot and not fine-tuned on aerial imagery, so it is a way to
    explore a scene, not a detector. Anything you would report, verify.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True,
                        help="A GeoTIFF of aerial imagery, 1 m or better.")
    parser.add_argument("--out", required=True, help="Directory for the scene.")
    parser.add_argument("--dim", type=int, default=64,
                        help="Dimensions to keep after PCA. 64 is DinoSats' choice: "
                             "1024 raw dimensions compress to 64 bytes a patch with "
                             "little loss, and that is what makes the scene a "
                             "gigabyte rather than sixteen.")
    parser.add_argument("--patch", type=int, default=16,
                        help="DINOv3 patch size in pixels.")
    parser.add_argument("--vocab", default=None,
                        help="A file of prompts, one per line, to precompute.")
    parser.add_argument("--weights", default="weights",
                        help="Where the DINOv3 and dino.txt weights are.")
    args = parser.parse_args()

    # Checked one at a time so the message names every one that is absent
    # rather than only the first.
    missing = [name for name in ("torch", "rasterio", "numpy")
               if importlib.util.find_spec(name) is None]
    if missing:
        print("This needs " + ", ".join(missing) + ".", file=sys.stderr)
        print("    pip install torch rasterio numpy scikit-learn", file=sys.stderr)
        return 2

    import rasterio
    import torch

    if not torch.cuda.is_available():
        print("No CUDA device. Embedding a city on a CPU takes days rather than "
              "hours; this refuses rather than letting you find that out "
              "overnight.", file=sys.stderr)
        return 2

    weights = Path(args.weights)
    needed = weights / "hf-dinov3-vitl16-lvd1689m"
    if not needed.exists():
        print(f"The DINOv3 weights are not at {needed}.", file=sys.stderr)
        print("They are gated on Hugging Face — accept the licence, then:", file=sys.stderr)
        print("    hf download facebook/dinov3-vitl16-pretrain-lvd1689m \\",
              file=sys.stderr)
        print(f"        --local-dir {needed}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.image) as src:
        bounds = src.bounds
        if src.crs and src.crs.to_epsg() != 4326:
            print(f"The image is in {src.crs}. The viewer places a scene by its "
                  "WGS84 bounds, so reproject it first:", file=sys.stderr)
            print(f"    gdalwarp -t_srs EPSG:4326 {args.image} reprojected.tif",
                  file=sys.stderr)
            return 2
        resolution = abs(src.transform.a) * 111320
        if resolution > 2.5:
            print(f"The image is about {resolution:.1f} m a pixel. DINOv3 was "
                  "trained on photographs, and a patch that coarse is not "
                  "recognisable as anything. This needs 1 m or better.",
                  file=sys.stderr)
            return 2

    print(f"Image: {src.width}x{src.height} at about {resolution:.2f} m")
    print(f"Bounds: {bounds.left:.5f}, {bounds.bottom:.5f}, "
          f"{bounds.right:.5f}, {bounds.top:.5f}")
    print()
    print("The embedding pass itself is deliberately not written here.")
    print()
    print("Running DINOv3 over a city is a few hundred lines that depend on the")
    print("exact weights, the exact dinov3 repo revision and how much memory the")
    print("GPU has — and every one of those changes faster than this file would")
    print("be updated. Writing a version that silently produced wrong vectors")
    print("would be worse than writing none.")
    print()
    print("The reference implementation is DinoSats, which this scene format is")
    print("deliberately identical to:")
    print()
    print("    https://github.com/calebrob6/dinosats")
    print("    scripts/embed.py        the imagery pass")
    print("    scripts/embed_vocab.py  the prompt table")
    print("    scripts/make_mosaic.py  the tiling")
    print()
    print("Run those against Ghana imagery and the output drops straight in. The")
    print("manifest the viewer wants is written below as a template — fill in")
    print("the numbers that pass produces.")

    manifest = {
        "name": Path(args.image).stem,
        "bounds": [bounds.left, bounds.bottom, bounds.right, bounds.top],
        "width": None,
        "height": None,
        "dim": args.dim,
        "patch_metres": round(resolution * args.patch, 2),
        "embeddings": "scene.u8",
        "prompts": "prompts.json",
        "scale": None,
        "offset": None,
        "logit_scale": 100,
        "attribution": "Imagery: fill this in. Embeddings: DINOv3 (Meta), "
                       "text: dino.txt. Method after DinoSats (Robinson, "
                       "Corley, Rolih).",
        "_note": "width, height, scale and offset come from the embedding pass. "
                 "scale and offset are per-dimension arrays of length dim: a "
                 "stored byte b becomes (b - 128) * scale[d] + offset[d]."
    }
    (out / "scene.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print()
    print(f"Wrote the manifest template to {out / 'scene.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
