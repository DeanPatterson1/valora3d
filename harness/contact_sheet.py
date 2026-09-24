"""Contact sheets: a case's key frames left to right under a label strip, for grading at a glance."""
from pathlib import Path

from PIL import Image, ImageDraw

LABEL_H = 24
MAX_SHEET_FRAMES = 12


def sheet(paths, label, out, thumb_h=256):
    thumbs = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        w = max(1, round(im.width * thumb_h / im.height))
        thumbs.append(im.resize((w, thumb_h), Image.LANCZOS))
    canvas = Image.new("RGB", (max(1, sum(t.width for t in thumbs)), thumb_h + LABEL_H), (16, 16, 16))
    ImageDraw.Draw(canvas).text((4, 5), str(label), fill=(230, 230, 230))
    x = 0
    for t in thumbs:
        canvas.paste(t, (x, LABEL_H))
        x += t.width
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def case_sheet(case_dir, out=None, thumb_h=256):
    case_dir = Path(case_dir)
    paths = sorted((case_dir / "beauty").glob("*.png"))
    if len(paths) > MAX_SHEET_FRAMES:  # a full render: evenly spaced frames, first and last kept
        paths = [paths[round(k * (len(paths) - 1) / (MAX_SHEET_FRAMES - 1))] for k in range(MAX_SHEET_FRAMES)]
    return sheet(paths, case_dir.name, out or case_dir / "contact_sheet.png", thumb_h)
