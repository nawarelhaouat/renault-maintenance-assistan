import sys
from pathlib import Path

import cv2
import numpy as np
import qrcode
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.db import query

OUT = Path(__file__).resolve().parent / "photos"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(42)


def font(size):
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def make_plate(m, with_qr=True):
    W, H = 900, 520
    img = Image.new("RGB", (W, H), (190, 192, 196))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, W - 9, H - 9], outline=(60, 60, 60), width=6)
    d.text((40, 30), "RENAULT GROUP TANGER", font=font(34), fill=(20, 20, 20))
    lines = [
        f"{m['manufacturer']} {m['model_name']}",
        f"S/N: {m['serial_number']}",
        f"ID: {m['asset_tag']}",
        f"Install: {m['install_date'].year}",
    ]
    for i, t in enumerate(lines):
        d.text((40, 110 + i * 70), t, font=font(40), fill=(15, 15, 15))
    if with_qr:
        qr = qrcode.make(m["asset_tag"]).convert("RGB").resize((260, 260))
        img.paste(qr, (W - 300, 200))
    return img


def field_photo(plate_pil):
    plate = cv2.cvtColor(np.array(plate_pil), cv2.COLOR_RGB2BGR)
    h, w = plate.shape[:2]
    canvas = np.full((960, 1280, 3), 70, np.uint8)
    canvas = cv2.add(canvas, rng.integers(0, 40, canvas.shape, dtype=np.uint8))
    M = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-10, 10), 1.0)
    plate = cv2.warpAffine(plate, M, (w, h), borderValue=(70, 70, 70))
    canvas[220:220 + h, 190:190 + w] = plate
    canvas = cv2.GaussianBlur(canvas, (5, 5), 0)
    noise = rng.normal(0, 6, canvas.shape)
    canvas = canvas.astype(np.float32) * rng.uniform(0.75, 1.15) + noise
    return np.clip(canvas, 0, 255).astype(np.uint8)


rows = query("SELECT asset_tag, serial_number, manufacturer, model_name, install_date FROM machine_summary ORDER BY asset_tag")
for m in rows:
    tag = m["asset_tag"]
    cv2.imwrite(str(OUT / f"{tag}_field.jpg"), field_photo(make_plate(m, True)), [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(str(OUT / f"{tag}_noqr.jpg"), field_photo(make_plate(m, False)), [cv2.IMWRITE_JPEG_QUALITY, 90])
print(f"OK: {len(rows) * 2} images dans {OUT}")