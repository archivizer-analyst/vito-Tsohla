"""Cut the crops of crops.json out of the render, sized for the image generator.

    python tools/cut.py <job>/crops.json

For each crop: the skill's box around the people, plus context around it (CONTEXT of its size on
every side, more for small crops so they are upscaled at most MAX_UP times), widened to the generator's aspect limits (1:3 .. 3:1) and to the exact aspect of the
size it is sent at. The send size is in multiples of 16 with MIN_PX .. MAX_PX pixels: small crops
are upscaled, crops above MAX_PX are downscaled. The generator returns the same size; the
assembly scales it back onto `box`.

Writes <job>/crops/<id>.png (at the send size) and <job>/crops/index.json:
  {"render", "size", "crops": [{"id", "file", "box" (render px, after widening), "people_box"
   (the skill's box), "size" (send size [w, h]), "scale" (send px per render px), "people",
   "plane", "desc", "notes"?}]}
"""
import json
import math
import os
import sys

from PIL import Image

CONTEXT = 0.12          # of the people box, on every side
MIN_PX = 655_360        # GPT Image 2.5 custom sizes: 655,360 .. 8,294,400 pixels
MAX_PX = 3_686_400      # 2560x1440: above it the sizes are experimental
MAX_EDGE = 3840
ASPECT = (1 / 3, 3.0)
MAX_UP = 4.0            # a small crop takes in more context rather than being upscaled more


def _r16(v):
    return max(16, int(round(v / 16)) * 16)


def send_size(w, h):
    """The generator size [W, H] for a box of w x h render px: multiples of 16, MIN_PX..MAX_PX."""
    s = 1.0
    if w * h < MIN_PX:
        s = math.sqrt(MIN_PX / (w * h))
    elif w * h > MAX_PX:
        s = math.sqrt(MAX_PX / (w * h))
    s = min(s, MAX_EDGE / max(w, h))
    W, H = _r16(w * s), _r16(h * s)
    while W * H < MIN_PX:                # rounding fell under the minimum
        if W / H < w / h:
            W += 16
        else:
            H += 16
    while W * H > MAX_PX or max(W, H) > MAX_EDGE:
        if W / H > w / h:
            W -= 16
        else:
            H -= 16
    return W, H


def _grow(lo, hi, length, limit):
    """Widen [lo, hi] to `length` around its centre, shifted to stay inside 0..limit."""
    length = min(length, limit)
    c = (lo + hi) / 2
    lo = c - length / 2
    lo = min(max(lo, 0), limit - length)
    return lo, lo + length


def fit_box(box, W, H):
    """The crop box: people box + context, clamped to the generator's aspect range, inside W x H."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    x0, x1 = _grow(x0, x1, w * (1 + 2 * CONTEXT), W)
    y0, y1 = _grow(y0, y1, h * (1 + 2 * CONTEXT), H)
    w, h = x1 - x0, y1 - y0
    if w / h < ASPECT[0]:
        x0, x1 = _grow(x0, x1, h * ASPECT[0], W)
    elif w / h > ASPECT[1]:
        y0, y1 = _grow(y0, y1, w / ASPECT[1], H)
    w, h = x1 - x0, y1 - y0
    k = math.sqrt(MIN_PX / (w * h)) / MAX_UP
    if k > 1:
        x0, x1 = _grow(x0, x1, w * k, W)
        y0, y1 = _grow(y0, y1, h * k, H)
    return [x0, y0, x1, y1]


def match_aspect(box, ratio, W, H):
    """Widen the box to exactly `ratio` = w/h (the send size's), inside W x H; shrink if it can't."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w / h < ratio:
        x0, x1 = _grow(x0, x1, h * ratio, W)
        if (x1 - x0) / h < ratio - 1e-6:            # hit the render's width: cut the height
            y0, y1 = _grow(y0, y1, (x1 - x0) / ratio, H)
    else:
        y0, y1 = _grow(y0, y1, w / ratio, H)
        if w / (y1 - y0) > ratio + 1e-6:
            x0, x1 = _grow(x0, x1, (y1 - y0) * ratio, W)
    return [round(x0), round(y0), round(x1), round(y1)]


def main(crops_path):
    job = os.path.dirname(os.path.abspath(crops_path))
    doc = json.load(open(crops_path, encoding="utf-8"))
    img = Image.open(os.path.join(job, doc["render"])).convert("RGB")
    W, H = img.size
    out_dir = os.path.join(job, "crops")
    os.makedirs(out_dir, exist_ok=True)
    index = []
    for c in doc["crops"]:
        box = fit_box(c["box"], W, H)
        sw, sh = send_size(box[2] - box[0], box[3] - box[1])
        box = match_aspect(box, sw / sh, W, H)
        name = c["id"] + ".png"
        img.crop(box).resize((sw, sh), Image.LANCZOS).save(os.path.join(out_dir, name))
        entry = {"id": c["id"], "file": name, "box": box, "people_box": c["box"], "size": [sw, sh],
                 "scale": round(sw / (box[2] - box[0]), 3), "people": c["people"],
                 "plane": c["plane"], "desc": c["desc"]}
        if c.get("notes"):
            entry["notes"] = c["notes"]
        index.append(entry)
        print(f"{c['id']}: box {box} -> {sw}x{sh} (x{entry['scale']})")
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"render": doc["render"], "size": [W, H], "crops": index}, f, ensure_ascii=False, indent=2)
    print(f"{len(index)} crops -> {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1])
