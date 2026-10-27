"""Assemble the result in Photoshop: the render plus a masked layer per enhanced crop.

    python tools/assemble.py <job> [--feather 1] [--keep-open]

Reads <job>/crops/index.json and the results in <job>/enhanced/; writes <job>/result.psd (the
render as the background, above it the group "people_enhanced" with one layer per crop named
"<id> <desc>", masked by Photoshop's Select Subject) and <job>/result.jpg. Layers are pasted far first: a crop whose box ends lower on the
render (nearer the camera) lies above. Crops without an enhanced result are left out and listed.

An enhanced result may be any size and any of EXTS (the generator, an upscaler or a person may
have made it): it is scaled onto its box. A result whose aspect differs from the box's by more
than ASPECT_TOL is stretched the same way and reported.

Runs tools/assemble.jsx in Photoshop through COM (Windows, Photoshop installed). When Photoshop
is not running, it is started hidden (only its splash shows for a moment) and quit at the end;
a Photoshop already running is used as it is, visible.
"""
import argparse
import json
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GROUP = "people_enhanced"
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")
ASPECT_TOL = 0.02       # result vs box aspect: beyond this the stretch is reported


def _p(path):
    return os.path.abspath(path).replace("\\", "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--feather", type=float, default=1.0, help="mask edge feather, render px")
    ap.add_argument("--keep-open", action="store_true", help="leave a Photoshop this script started running")
    a = ap.parse_args()

    job = os.path.abspath(a.job)
    index = json.load(open(os.path.join(job, "crops", "index.json"), encoding="utf-8"))
    crops, missing = [], []
    for c in sorted(index["crops"], key=lambda c: c["box"][3]):
        found = [p for p in (os.path.join(job, "enhanced", c["id"] + e) for e in EXTS) if os.path.isfile(p)]
        if not found:
            missing.append(c["id"])
            continue
        w, h = Image.open(found[0]).size
        bw, bh = c["box"][2] - c["box"][0], c["box"][3] - c["box"][1]
        if abs((w / h) / (bw / bh) - 1) > ASPECT_TOL:
            print(f"{c['id']}: WARNING the result is {w}x{h}, aspect {w / h:.3f}, but its box is "
                  f"{bw}x{bh}, aspect {bw / bh:.3f} -- stretched onto the box, check the layer")
        crops.append({"id": c["id"], "name": f"{c['id']} {c['desc']}"[:200], "file": _p(found[0]),
                      "box": c["box"], "feather": a.feather})
    if missing:
        print("not enhanced, left out:", " ".join(missing))
    if not crops:
        sys.exit("nothing to assemble")
    manifest = {"render": _p(os.path.join(job, index["render"])), "crops": crops, "group": GROUP,
                "psd": _p(os.path.join(job, "result.psd")), "jpg": _p(os.path.join(job, "result.jpg")),
                "report": _p(os.path.join(job, "enhanced", "assemble.txt"))}
    man_path = os.path.join(job, "enhanced", "assemble.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    # A Photoshop this script starts works hidden and quits at the end; one already running (a
    # person may be working in it) stays as it is.
    ps = ("$was = [bool](Get-Process Photoshop -ErrorAction SilentlyContinue); "
          "$ps = New-Object -ComObject Photoshop.Application; "
          "if (-not $was) { $ps.Visible = $false }; "
          f"try {{ $null = $ps.DoJavaScriptFile('{_p(os.path.join(HERE, 'assemble.jsx'))}', @('{_p(man_path)}')) }} "
          f"finally {{ if (-not $was -and -not ${'true' if a.keep_open else 'false'}) {{ $ps.Quit() }} }}")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Photoshop failed:\n{r.stdout}\n{r.stderr}")
    report = open(manifest["report"], encoding="utf-8").read().strip().splitlines()
    bad = [line for line in report if not line.endswith("\tmasked")]
    for line in report:
        print(line.replace("\t", ": "))
    print(f"-> {manifest['psd']}\n-> {manifest['jpg']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
