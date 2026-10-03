import difflib
import re
from functools import lru_cache

import cv2
import numpy as np

from app.db import query

TAG_RE = re.compile(r"TNG-[A-Z]{3}-\d{4}")

CATEGORIES = {
    "Robot": "an industrial 6-axis robot arm in a car factory",
    "Presse": "a large hydraulic stamping press",
    "Visseuse": "a handheld industrial torque screwdriver",
    "Automate": "an industrial PLC control cabinet",
    "Robot peinture": "a painting robot in a paint booth",
}


@lru_cache(maxsize=1)
def _known():
    rows = query("SELECT asset_tag, serial_number FROM machines")
    return {r["asset_tag"] for r in rows}, {r["serial_number"]: r["asset_tag"] for r in rows}


# ---------- 1. QR code ----------
def _decode_qr(img):
    det = cv2.QRCodeDetector()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    for variant in (img, gray, cv2.resize(gray, None, fx=1.5, fy=1.5), thr):
        text, _, _ = det.detectAndDecode(variant)
        if text:
            return text.strip().upper()
    return None


# ---------- 2. OCR de la plaque ----------
@lru_cache(maxsize=1)
def _reader():
    import easyocr
    return easyocr.Reader(["en", "fr"], gpu=False)  # modèles téléchargés une seule fois


def _best(tokens, universe):
    best = (None, 0.0)
    for tok in tokens:
        for key, tag in universe.items():
            r = difflib.SequenceMatcher(None, tok, key).ratio()
            if r > best[1]:
                best = (tag, r)
    return best


def _ocr(img):
    tags, serials = _known()
    text = " ".join(_reader().readtext(img, detail=0)).upper()
    tokens = re.findall(r"[A-Z0-9\-]{6,}", text)
    tag_c, tag_r = _best(tokens, {t: t for t in tags})
    sn_c, sn_r = _best(tokens, serials)
    tag_c = tag_c if tag_r >= 0.8 else None
    sn_c = sn_c if sn_r >= 0.8 else None
    if not tag_c and not sn_c:
        return None
    if tag_c and sn_c and tag_c == sn_c:           # ID et S/N concordent : fiable
        return {"method": "OCR plaque (ID + S/N)", "asset_tag": tag_c,
                "confidence": max(tag_r, sn_r), "needs_confirmation": False, "ocr_text": text}
    tag, r = (tag_c, tag_r) if tag_r >= sn_r else (sn_c, sn_r)
    return {"method": "OCR plaque", "asset_tag": tag, "confidence": r,
            "needs_confirmation": r < 1.0, "ocr_text": text}   # lecture inexacte : à confirmer


# ---------- 3. Fallback vision (catégorie seulement) ----------
@lru_cache(maxsize=1)
def _clip():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("clip-ViT-B-32")


def _classify(img):
    from PIL import Image
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    model = _clip()
    ie = model.encode(pil, normalize_embeddings=True)
    te = model.encode(list(CATEGORIES.values()), normalize_embeddings=True)
    p = np.exp(100 * (te @ ie))
    p /= p.sum()
    i = int(p.argmax())
    return list(CATEGORIES)[i], float(p[i])


def identify(data: bytes) -> dict:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"method": None, "error": "Image illisible"}

    tags, _ = _known()
    qr = _decode_qr(img)
    if qr:
        m = TAG_RE.search(qr)
        if m and m.group() in tags:
            return {"method": "QR code", "asset_tag": m.group(), "confidence": 0.99,
                    "needs_confirmation": False}

    ocr = _ocr(img)
    if ocr:
        return ocr

    cat, p = _classify(img)
    cands = query("SELECT asset_tag, manufacturer, model_name, line_name FROM machine_summary "
                  "WHERE category = %s ORDER BY asset_tag LIMIT 15", (cat,))
    return {"method": "Vision (CLIP, catégorie seulement)", "asset_tag": None, "category": cat,
            "confidence": p, "needs_confirmation": True, "candidates": cands}