# Searching imagery by description

**Home → Ghana Data → Search Imagery.** Type *rooftops* and the places that
look like rooftops light up.

The method is [DinoSats](https://github.com/calebrob6/dinosats), by Caleb
Robinson, Isaac Corley and Blaž Rolih. An image model has already turned
every patch of imagery into a vector; a text model turns your words into a
vector of the same kind; the score is how similar the two are. No server, no
model inference on the imagery at search time, and no labels anywhere.

**There is no scene for Ghana yet.** The viewer carries the search; the scene
is a few hours of GPU time that somebody with a GPU has to give. This page
says how.

---

## Why ship the search before the scene

The scene is a day's work for one person with the right hardware and an
accepted Hugging Face licence. The client is the part that has to be right,
and the part nobody can contribute in an afternoon. Building it now means the
scene is the only thing missing, and the moment one exists its address goes
in a box and everything works.

The scene format here is deliberately identical to DinoSats', so a scene
built with their scripts drops straight in.

---

## How the score works

```
score = σ( s·cos(q, x) − logΣexp(s·cos(b, x)) )     over background prompts b
```

A raw cosine between a prompt and a patch says how much the patch looks like
the word, on a scale whose zero means nothing. The background correction asks
instead whether the patch looks *more like rooftops than like water, road,
trees or bare ground* — which is the question anyone actually has, and which
is the difference between a readable heatmap and a wash.

The background prompts therefore decide what a score means. The DinoSats
write-up gives the clearest example: adding *barge* to the background list
cleaned up false positives over open water, and also made ships look like
barges. Changing them is a real analytical choice, not a display setting.

`logit_scale` is the text model's temperature, 100 for dino.txt. The manifest
can override it.

---

## The scene format

Three static files, served over HTTP from anywhere.

```
scene.json      the manifest
scene.u8        width × height × dim bytes
prompts.json    { "rooftops": [ … dim floats … ], … }
```

```json
{
  "name": "Accra 2024",
  "bounds": [-0.33, 5.50, -0.05, 5.68],
  "width": 2800, "height": 1800, "dim": 64,
  "patch_metres": 9.6,
  "embeddings": "scene.u8",
  "prompts": "prompts.json",
  "scale": [ … dim floats … ],
  "offset": [ … dim floats … ],
  "logit_scale": 100,
  "attribution": "Imagery: …  Embeddings: DINOv3 (Meta), text: dino.txt."
}
```

A stored byte `b` becomes `(b − 128) × scale[d] + offset[d]`. Quantising to a
byte per dimension is what makes a scene a gigabyte rather than sixteen, and
the DinoSats measurements say 8-bit weights are indistinguishable from fp32.

Three files rather than one because the vectors are the big part and never
change, while the prompt table is small and grows as people find words that
work. A new prompt then costs a few kilobytes, not a re-download.

---

## Building a scene

`pipelines/06_embed_imagery.py` checks everything and writes the manifest
template. The embedding pass itself is deliberately left to the DinoSats
scripts, because it depends on the exact weights, the exact `dinov3` revision
and how much memory the GPU has — all of which change faster than a copy
here would be updated, and a copy that silently produced wrong vectors would
be worse than no copy.

What it needs:

- a CUDA GPU with 16 GB or more
- the [DINOv3 weights](https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m),
  which are gated and need an accepted licence
- the dino.txt text head, for turning words into vectors of the same kind
- **imagery at a metre or better**

That last one is the real constraint for Ghana. Sentinel-2 at 10 m does not
work: DINOv3 was trained on photographs, and a 10 m patch of Accra is not
recognisable as anything to a model that has seen photographs. What would
work is drone imagery, a commercial tasking, or an aerial survey — and Ghana
has had several, held by the Survey and Mapping Division and by the mining
companies.

---

## What it is good at

From the DinoSats findings, which are worth repeating because they set
expectations honestly:

- **Large, distinctive things seen from above.** Runways, quarries, sports
  fields, large rooftops, open water. For Ghana that would be the Akosombo
  dam, Tema harbour, the Obuasi workings, the irrigated blocks at Kpong.
- **Word choice matters more than it should.** Against Overture building
  footprints, *rooftops* matched a linear probe trained on about a thousand
  labelled patches, and beat *buildings* and *houses* by a wide margin. There
  is no way to know which word wins in advance. Try several.
- **Zero-shot is worth several hundred labels** — but it is not a detector.
  dino.txt was trained on web photographs and has not been fine-tuned on
  aerial imagery. It is a way to explore a scene. Anything you would report,
  verify.
- **Position leaks into the vectors.** DINOv3's patch tokens encode where
  they sit in their window, and over open water that is most of the signal.
  Removing that subspace raised zero-shot average precision for buildings
  from 0.61 to 0.77 in their tests. If you build a scene, do it — the
  manifest can carry the projection.

---

## Checking it

`tests/imagery.cjs` builds a 16 × 16 × 8 fixture scene whose answer is known:
four quadrants, three of them made to match a background prompt and one to
match the query. The matching quadrant must score near 1 and the rest near 0.

That proves the arithmetic between a prompt and a patch, and nothing else.
Whether DINOv3 thinks a Ghanaian rooftop looks like the word *rooftop* is a
question for the day somebody builds a real scene.

---

## Credit

The method, the scene format and the findings above are
[DinoSats](https://github.com/calebrob6/dinosats) — Caleb Robinson, Isaac
Corley and Blaž Rolih — which is MIT licensed. DINOv3 is Meta's; dino.txt is
from *Towards Zero-Shot Image Recognition with DINOv2*. No code was copied:
the client here is written against the same file format so that scenes are
interchangeable.
