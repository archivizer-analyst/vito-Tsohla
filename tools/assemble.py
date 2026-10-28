"""Assemble the result in Photoshop: the render plus a masked layer per enhanced crop.

    python tools/assemble.py <job> [--feather 1] [--quit] [--scratch-dir D ...] [--scratch-gb 20]

Reads <job>/crops/index.json and the results in <job>/enhanced/; writes <job>/result.psd (the
render as the background, above it the group "people_enhanced" with one layer per crop named
"<id> <desc>", masked by Photoshop's Select Subject) and <job>/result.jpg. Layers are pasted far
first: a crop whose box ends lower on the render (nearer the camera) lies above. Crops without an
enhanced result are left out and listed.

Every layer is a smart object holding the enhanced result at its own resolution, scaled onto its
box: stretching it to fix proportions or upscaling the render later loses nothing. A result may be
any size and any of EXTS (the generator, an upscaler or a person may have made it). A result whose
aspect differs from the box's by more than ASPECT_TOL is stretched the same way and reported.

Photoshop. tools/assemble.jsx runs in it through COM (Windows, Photoshop installed). When it is
not running, it is started hidden (only its splash shows for a moment); a Photoshop already
running is used as it is. It stays open after the assembly, so the next one does not wait for it
to start (--quit closes one this script started).
Its scratch files ("Photoshop Temp*") grow while it runs and are deleted by Photoshop itself only
when it quits. After each assembly the script purges Photoshop's caches and, when the scratch
files in the scratch folders (%TEMP% and every --scratch-dir: set them to the scratch disks in
Photoshop's preferences) exceed --scratch-gb and no document is open, quits Photoshop; the next
assembly starts it again. Nothing is deleted by this script.
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
SCRATCH_GB = 20         # Photoshop's scratch files above this: quit it when idle
MAX_COVER = 0.9         # a mask over more of its crop has taken the crop, not the people: cut.py
                        # leaves context round the people on every side


def _p(path):
    return os.path.abspath(path).replace("\\", "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--feather", type=float, default=1.0, help="mask edge feather, render px")
    ap.add_argument("--quit", action="store_true", help="quit a Photoshop this script started")
    ap.add_argument("--scratch-dir", nargs="*", default=[], help="Photoshop scratch disks besides %%TEMP%%")
    ap.add_argument("--scratch-gb", type=float, default=SCRATCH_GB)
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
                "max_cover": MAX_COVER,
                "psd": _p(os.path.join(job, "result.psd")), "jpg": _p(os.path.join(job, "result.jpg")),
                "report": _p(os.path.join(job, "enhanced", "assemble.txt"))}
    man_path = os.path.join(job, "enhanced", "assemble.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    # Start Photoshop hidden if it is not running; keep it open. Then, if its scratch files have
    # grown past the limit and no document is open, quit it: only Photoshop frees them.
    dirs = [os.environ.get("TEMP", "")] + a.scratch_dir
    ps = ("$was = [bool](Get-Process Photoshop -ErrorAction SilentlyContinue); "
          "$ps = New-Object -ComObject Photoshop.Application; "
          "if (-not $was) { $ps.Visible = $false }; "
          f"try {{ $null = $ps.DoJavaScriptFile('{_p(os.path.join(HERE, 'assemble.jsx'))}', @('{_p(man_path)}')) }} "
          "finally { "
          f"$s = (Get-ChildItem -LiteralPath {', '.join(repr(_p(d)) for d in dirs if d)} -Filter 'Photoshop Temp*' "
          "-File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; "
          "Write-Output ('scratch ' + [math]::Round($s / 1GB, 2)); "
          f"if ((-not $was -and ${'true' if a.quit else 'false'}) -or "
          f"($s -gt {int(a.scratch_gb * 2 ** 30)} -and $ps.Documents.Count -eq 0)) "
          "{ $ps.Quit(); Write-Output 'photoshop quit' } }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Photoshop failed:\n{r.stdout}\n{r.stderr}")
    for line in r.stdout.splitlines():
        if line.startswith(("scratch", "photoshop quit")):
            print(line.strip() + (" GB of Photoshop scratch files" if line.startswith("scratch") else ""))
    report = open(manifest["report"], encoding="utf-8").read().strip().splitlines()
    bad = [line for line in report if line.split("\t")[1] != "masked" and not line.startswith("*\tphotoshop")]
    for line in report:
        print(line.replace("\t", ": ", 1).replace("\t", " "))
    if any("\tbad mask" in line for line in report):
        print("bad mask: Select Subject took the whole crop; the layer is hidden. Try Select > Subject "
              "on that enhanced image by hand in the same Photoshop, mask the layer by hand if it fails too")
    print(f"-> {manifest['psd']}\n-> {manifest['jpg']}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
