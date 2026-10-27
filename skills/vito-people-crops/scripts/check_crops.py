"""Check a Vito crops.json: errors to fix, warnings to read.

    python check_crops.py <crops.json>

Exit code 1 when there are errors.
"""
import json
import os
import re
import sys

from PIL import Image

PLANES = ("near", "mid", "far")


def _area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def _inter(a, b):
    return _area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def check(path):
    errors, warnings = [], []
    doc = json.load(open(path, encoding="utf-8"))
    if doc.get("version") != 1:
        errors.append("version must be 1")
    render = os.path.join(os.path.dirname(os.path.abspath(path)), doc.get("render", ""))
    if not os.path.isfile(render):
        errors.append(f"render not found: {render}")
        W, H = doc.get("size", [0, 0])
    else:
        W, H = Image.open(render).size
        if list(doc.get("size", [])) != [W, H]:
            errors.append(f"size {doc.get('size')} but the render is {[W, H]}")
    crops = doc.get("crops", [])
    if not crops:
        errors.append("no crops")
    ids = set()
    for c in crops:
        cid = c.get("id", "?")
        if not re.fullmatch(r"c\d{2,}", cid):
            errors.append(f"{cid}: id must be c01, c02, ...")
        if cid in ids:
            errors.append(f"{cid}: duplicate id")
        ids.add(cid)
        b = c.get("box")
        if not (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)):
            errors.append(f"{cid}: box must be [x0, y0, x1, y1]")
            continue
        if not (b[0] < b[2] and b[1] < b[3]):
            errors.append(f"{cid}: box {b} is empty or inverted")
        if b[0] < 0 or b[1] < 0 or b[2] > W or b[3] > H:
            errors.append(f"{cid}: box {b} runs outside the render {W}x{H}")
        if not isinstance(c.get("people"), int) or c["people"] < 1:
            errors.append(f"{cid}: people must be a count >= 1")
        if c.get("plane") not in PLANES:
            errors.append(f"{cid}: plane must be one of {PLANES}")
        if not c.get("desc"):
            errors.append(f"{cid}: desc is empty")
        h = b[3] - b[1]
        if h < 24:
            warnings.append(f"{cid}: box only {h} px tall -- too small to enhance, or merge it with a group near it")
        if c.get("plane") == "near" and c.get("people", 1) > 1 and _area(b) > 0.25 * W * H:
            warnings.append(f"{cid}: a near crop with {c['people']} people over a quarter of the render -- "
                            "are their silhouettes really overlapping?")
    order = [c["box"][0] for c in crops if isinstance(c.get("box"), list) and len(c["box"]) == 4]
    if order != sorted(order):
        warnings.append("crops are not ordered left to right")
    for i, a in enumerate(crops):
        for b in crops[i + 1:]:
            try:
                share = _inter(a["box"], b["box"]) / max(1, min(_area(a["box"]), _area(b["box"])))
            except (KeyError, TypeError, IndexError):
                continue
            if share > 0.15:
                warnings.append(f"{a['id']} and {b['id']}: boxes overlap by {share:.0%} of the smaller one -- "
                                "if people overlap there, merge them into one crop")
    for s in doc.get("skipped", []):
        if not s.get("why"):
            errors.append(f"skipped {s.get('box')}: no why")
    return errors, warnings


def main():
    errors, warnings = check(sys.argv[1])
    for e in errors:
        print("ERROR  ", e)
    for w in warnings:
        print("WARNING", w)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
