"""Check a Vito prompts.json against crops/index.json: errors to fix, warnings to read.

    python check_prompts.py <prompts.json> <crops/index.json>

Exit code 1 when there are errors.
"""
import json
import sys

KEEP_WORDS = ("same position", "pose", "do not add", "lighting")
STYLE_WORDS = ("cinematic", "dramatic", "masterpiece", "8k", "ultra detailed", "hdr")


def check(prompts_path, index_path):
    errors, warnings = [], []
    doc = json.load(open(prompts_path, encoding="utf-8"))
    index = json.load(open(index_path, encoding="utf-8"))
    if doc.get("version") != 1:
        errors.append("version must be 1")
    req = doc.get("request", {})
    if not req.get("text"):
        warnings.append("request.text is empty -- no request means realism only; say so in summary")
    if not req.get("summary"):
        errors.append("request.summary is empty")
    keep = set(req.get("keep", []))
    want = [c["id"] for c in index["crops"] if c["id"] not in keep]
    got = [c.get("id") for c in doc.get("crops", [])]
    for cid in keep - {c["id"] for c in index["crops"]}:
        errors.append(f"request.keep: {cid} is not a crop")
    for cid in set(want) - set(got):
        errors.append(f"{cid}: no prompt (and not in request.keep)")
    for cid in set(got) - set(want):
        errors.append(f"{cid}: prompt for a crop that is not in index.json or is in request.keep")
    if len(got) != len(set(got)):
        errors.append("duplicate crop ids")
    if [g for g in got if g in want] != [w for w in want if w in got]:
        warnings.append("crops are not in index.json's order")
    plane = {c["id"]: c.get("plane") for c in index["crops"]}
    for c in doc.get("crops", []):
        p = (c.get("prompt") or "").strip()
        cid = c.get("id", "?")
        if not p:
            errors.append(f"{cid}: empty prompt")
            continue
        low = p.lower()
        if not p.isascii():
            warnings.append(f"{cid}: the prompt is not plain English")
        for w in KEEP_WORDS:
            if w not in low:
                errors.append(f"{cid}: the prompt does not say to keep '{w}' -- the person may not land back")
        for w in STYLE_WORDS:
            if w in low:
                warnings.append(f"{cid}: style word '{w}' pulls away from the render")
        if plane.get(cid) == "far" and "small" not in low and "soft" not in low:
            warnings.append(f"{cid}: far crop -- say to keep the people as small and soft as they are")
    return errors, warnings


def main():
    errors, warnings = check(sys.argv[1], sys.argv[2])
    for e in errors:
        print("ERROR  ", e)
    for w in warnings:
        print("WARNING", w)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
