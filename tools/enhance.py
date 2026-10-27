"""Send every crop with its prompt to the image generator; save what comes back.

    python tools/enhance.py <job> [--workers 4] [--quality high] [--only c01 c03] [--force] [--dry-run]

Reads <job>/crops/index.json and <job>/prompts.json; writes <job>/enhanced/<id>.png and
<job>/enhanced/log.json (per crop: ok / error, seconds, the prompt sent). A crop whose result
already exists is skipped unless --force, so a run that stopped half way is just run again.

The generator: OpenAI Image API edits, model GPT Image 2.5 Flare, the crop as the input image,
the output size = the crop's size (tools/cut.py made it a valid custom size).
  OPENAI_API_KEY   the key
  VITO_IMAGES_URL  the edits endpoint, default https://api.openai.com/v1/images/edits
                   (point it at the Archivizer server's proxy when there is one)
  VITO_MODEL       default gpt-image-2.5-flare
"""
import argparse
import base64
import concurrent.futures as cf
import json
import os
import sys
import time

import requests

URL = os.environ.get("VITO_IMAGES_URL", "https://api.openai.com/v1/images/edits")
MODEL = os.environ.get("VITO_MODEL", "gpt-image-2.5-flare")
TRIES = 4
TIMEOUT = 300


def edit(png_path, prompt, size, quality, key):
    """One edit call; the result's PNG bytes. Retries rate limits and server errors."""
    data = {"model": MODEL, "prompt": prompt, "size": f"{size[0]}x{size[1]}", "quality": quality,
            "output_format": "png", "n": "1"}
    for attempt in range(TRIES):
        with open(png_path, "rb") as f:
            r = requests.post(URL, headers={"Authorization": f"Bearer {key}"}, data=data,
                              files={"image": (os.path.basename(png_path), f, "image/png")}, timeout=TIMEOUT)
        if r.status_code == 200:
            return base64.b64decode(r.json()["data"][0]["b64_json"])
        if r.status_code in (429, 500, 502, 503, 504) and attempt < TRIES - 1:
            wait = float(r.headers.get("retry-after", 0)) or 5 * 2 ** attempt
            time.sleep(wait)
            continue
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--quality", default="high", choices=["low", "medium", "high", "xhigh", "max", "auto"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    index = json.load(open(os.path.join(a.job, "crops", "index.json"), encoding="utf-8"))
    prompts = {c["id"]: c["prompt"] for c in json.load(open(os.path.join(a.job, "prompts.json"), encoding="utf-8"))["crops"]}
    out_dir = os.path.join(a.job, "enhanced")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "log.json")
    log = json.load(open(log_path, encoding="utf-8")) if os.path.isfile(log_path) else {}

    todo = []
    for c in index["crops"]:
        cid = c["id"]
        if cid not in prompts or (a.only and cid not in a.only):
            continue
        if os.path.isfile(os.path.join(out_dir, cid + ".png")) and not a.force:
            print(f"{cid}: already enhanced, skipped")
            continue
        todo.append(c)
    if a.dry_run:
        for c in todo:
            print(f"{c['id']}: POST {URL} model={MODEL} size={c['size'][0]}x{c['size'][1]} quality={a.quality}\n"
                  f"  {prompts[c['id']]}")
        return
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set")

    def run(c):
        t = time.time()
        png = edit(os.path.join(a.job, "crops", c["file"]), prompts[c["id"]], c["size"], a.quality, key)
        with open(os.path.join(out_dir, c["id"] + ".png"), "wb") as f:
            f.write(png)
        return time.time() - t

    failed = 0
    with cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = {pool.submit(run, c): c for c in todo}
        for fut in cf.as_completed(futures):
            cid = futures[fut]["id"]
            try:
                secs = fut.result()
                log[cid] = {"status": "ok", "seconds": round(secs, 1), "model": MODEL, "quality": a.quality,
                            "prompt": prompts[cid]}
                print(f"{cid}: ok, {secs:.0f} s")
            except Exception as e:  # noqa: BLE001 -- one crop's failure must not stop the others
                failed += 1
                log[cid] = {"status": "error", "error": str(e), "prompt": prompts[cid]}
                print(f"{cid}: ERROR {e}")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"{len(todo) - failed} enhanced, {failed} failed -> {out_dir}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
