---
name: vito-people-crops
description: Find the people on an architectural render for Vito and decide the crops they are enhanced in - one crop per person or per group whose silhouettes overlap, distant groups merged into one crop - and write crops.json with numbered crop boxes in render pixels. Use when a render's 3D people have to be cropped for enhancement, or when a crops.json has to be written, checked or fixed.
---

# Finding the people on a render and choosing the crops

Vito makes the 3D people on a render look real: every crop goes to the image generator, comes
back enhanced and is pasted over the render with a mask of the people in it. You decide **where
the crops are**: you find every person and group them into crops. Coordinates do not need to be
exact; a box a little looser than the people is right, the cutting script adds the context
around it.

You only write `crops.json`. Cutting, sizes for the generator and prompts come later.

## Input

- The render (any image format). Its size in pixels — print it with the grid script below.
- The specialist's request, only to know whether some people are excluded ("лише людей на
  терасі"); everything else in the request is for the prompt skill.

## 1. Look and measure

```
python skills/vito-people-crops/scripts/grid.py <render> <out.jpg>
python skills/vito-people-crops/scripts/grid.py <render> <out.jpg> --region x0 y0 x1 y1
```

The first draws a labelled pixel grid over the whole render; the second zooms into a region with
a finer grid. Pixels are in the render's own size: origin top-left, `x` to the right, `y` down.
Read boxes off the grid, zoom into crowded or distant parts. ±1 % of the render is enough.

Find **every** person: walking, sitting, standing behind glass, partly hidden by furniture or
plants, cut by the image edge, reflected in a mirror or glass next to them, tiny in the distance.

## 2. Group into crops

The aim: as few crops as possible, each with enough pixels on the people to enhance them.

- **Overlapping silhouettes → one crop.** People whose silhouettes touch or overlap (a couple
  arm in arm, a person in front of another, a child on a lap) are always one crop. Two crops
  over the same overlap would paste two different versions of the same pixels.
- **Distant groups → one crop.** People in the background (shorter than about 1/6 of the render
  height) standing within about one person's height of each other go into one crop, even when
  they do not touch. Many tiny crops give the generator too little to work with.
- **Near and mid-plane people apart → separate crops.** A person close to the camera gets their
  own crop, so their crop is not filled with empty space between them and someone else.
- **No crop of mostly empty space.** If merging two groups would make the people cover less than
  about a third of the box, keep them apart.
- **Crop boxes of different crops should not overlap** where there are people. If they do,
  merge them. Overlap of empty margins is fine.
- **Too small to enhance:** a person whose whole figure is under ~24 px tall and who has no one
  near to group with goes to `skipped` with the reason, not into a crop.
- Order crops from left to right; ids `c01`, `c02`, …

## 3. The box

`box: [x0, y0, x1, y1]` — the rectangle around all the people of the crop, head to feet (or to
the image edge), a few pixels loose. Not the context: the cutting script adds context around it
and adjusts the shape for the generator. Include a person's reflection or the shadow right at
their feet only if it touches them.

## Output

`crops.json` next to the render:

```json
{"version": 1, "render": "render.jpg", "size": [3840, 2160],
 "crops": [
  {"id": "c01", "box": [412, 980, 655, 1690], "people": 1, "plane": "near",
   "desc": "woman in a beige coat walking left, holding a phone"},
  {"id": "c02", "box": [1820, 1105, 2140, 1260], "people": 6, "plane": "far",
   "desc": "group of six people at the far end of the lobby, two seated on a bench",
   "notes": "a plant pot hides the legs of the rightmost seated man"}
 ],
 "skipped": [
  {"box": [3600, 1150, 3612, 1170], "why": "single figure 20 px tall at the far entrance"}
 ]}
```

| field | |
|---|---|
| `render` | the render's file name, relative to `crops.json` |
| `size` | the render's `[width, height]` in pixels |
| `id` | `c01`, `c02`, …, left to right |
| `box` | `[x0, y0, x1, y1]` around the people, render pixels |
| `people` | how many people are in the crop |
| `plane` | `near`, `mid` or `far` |
| `desc` | who is there and what they do, short, in English: the prompt skill uses it to tell the crops apart and to apply per-person requests |
| `notes` | optional: what hides or cuts the people (furniture in front, image edge, glass) |
| `skipped` | people not cropped, with `why` |

## Check

```
python skills/vito-people-crops/scripts/check_crops.py <crops.json>
```

Fix every error it prints; read every warning.
