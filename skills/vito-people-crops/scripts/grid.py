"""A pixel grid over a render (or a zoomed region of it), to read crop boxes off.

    python grid.py <render> <out.jpg>
    python grid.py <render> <out.jpg> --region x0 y0 x1 y1

Labels are the render's own pixels (origin top-left, x right, y down) whatever the picture is
scaled to. Prints the render's size.
"""
import argparse

from PIL import Image, ImageDraw, ImageFont

VIEW = 2000         # long side of the written picture, px


def _step(span, lines=16):
    """A round grid step giving about `lines` lines over `span` pixels."""
    raw = span / lines
    for s in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if s >= raw:
            return s
    return 1000


def _font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render")
    ap.add_argument("out")
    ap.add_argument("--region", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"))
    a = ap.parse_args()

    img = Image.open(a.render).convert("RGB")
    W, H = img.size
    print(f"render {W}x{H}")
    x0, y0, x1, y1 = a.region or (0, 0, W, H)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    img = img.crop((x0, y0, x1, y1))
    k = VIEW / max(img.size)
    img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    font = _font(max(12, VIEW // 110))
    step = _step(max(x1 - x0, y1 - y0))

    def label(xy, text):
        box = d.textbbox(xy, text, font=font)
        d.rectangle(box, fill=(0, 0, 0, 170))
        d.text(xy, text, fill=(255, 255, 0, 255), font=font)

    for v in range((x0 // step + 1) * step, x1, step):
        px = (v - x0) * k
        d.line([(px, 0), (px, img.height)], fill=(255, 0, 255, 110), width=1)
        label((px + 2, 2), str(v))
        label((px + 2, img.height - font.size - 6), str(v))
    for v in range((y0 // step + 1) * step, y1, step):
        py = (v - y0) * k
        d.line([(0, py), (img.width, py)], fill=(0, 255, 255, 110), width=1)
        label((2, py + 2), str(v))
        label((img.width - 6 * font.size // 2 - 8, py + 2), str(v))
    img.save(a.out, quality=90)
    print(f"grid step {step} px, region {x0},{y0},{x1},{y1} -> {a.out}")


if __name__ == "__main__":
    main()
