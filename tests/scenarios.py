"""Shared test scenarios: synthetic sample photos + the banner args for each."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SAMPLES = HERE / "samples"
GOLDEN = HERE / "golden"

# name -> (photo size, dict of build args). 'key' is the reference's scheme key.
SCENARIOS = {
    "braddock_landscape": ((1800, 1200), dict(
        title="Spring Seedling Sale", dt="Saturday, April 18 | 10am - 2pm",
        loc="Braddock", loc_key="braddock", cost="Free", yoff=0.5, nowrap=False)),
    "grc_portrait": ((1200, 1800), dict(
        title="Backyard Composting Workshop for Beginners and Experienced Gardeners",
        dt="May 3 | 6pm - 8pm", loc="Garden Resource Center", loc_key="grc", cost="$15", yoff=0.3, nowrap=False)),
    "other_2to1": ((1880, 940), dict(
        title="Virtual Garden Planning Q&A", dt="June 9 | 7pm",
        loc="Virtual", loc_key="other", cost=None, yoff=0.5, nowrap=False)),
    "shiloh_long_nowrap": ((1600, 1000), dict(
        title="An Extremely Long Event Title That Will Need The Shrink Logic To Fit",
        dt="July 12 | 9am - 1pm", loc="Shiloh", loc_key="shiloh", cost="Pay what you can", yoff=0.7, nowrap=True)),
}


def make_photo(name: str, size: tuple[int, int]) -> Path:
    SAMPLES.mkdir(exist_ok=True)
    path = SAMPLES / f"{name}.jpg"
    if path.exists():
        return path
    w, h = size
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    for y in range(h):  # vertical sky->grass gradient
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(90 + 60 * t), int(150 - 30 * t), int(220 - 150 * t)))
    for i in range(8):  # blobs so crops are distinguishable
        x, y = (i * 997) % w, (i * 613) % h
        d.ellipse((x, y, x + w // 6, y + w // 6), fill=(255 - 25 * i, 200, 40 * i))
    d.rectangle((w // 3, h // 3, w // 3 + 60, h // 3 + 60), fill=(0, 0, 0))
    im.save(path, quality=95)
    return path
