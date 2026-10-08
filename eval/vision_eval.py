import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import query  # noqa: E402
from app.vision.identify import identify  # noqa: E402

TAG = re.compile(r"(TNG-[A-Z]{3}-\d{4})")
SETS = [
    ("Avec QR code", ROOT / "data" / "photos", "*_field.jpg"),
    ("Sans QR code, plaque lisible", ROOT / "data" / "photos", "*_noqr.jpg"),
    # Photos réelles : nommer les fichiers <ÉTIQUETTE>__description.jpg, ex. TNG-PLC-0001__plaque.jpg
    ("Photographies de machines réelles", ROOT / "data" / "photos_reel", "*.jpg"),
]

parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=int, default=0, help="nombre maximal d'images par jeu (test rapide)")
args = parser.parse_args()

category_of = {m["asset_tag"]: m["category"] for m in query("SELECT asset_tag, category FROM machine_summary")}


def classify(res: dict, truth: str) -> str:
    if res.get("error"):
        return "read_error"
    tag = res.get("asset_tag")
    if tag:
        if tag == truth:
            return "confirm_ok" if res.get("needs_confirmation") else "direct_ok"
        return "confirm_wrong" if res.get("needs_confirmation") else "silent_error"
    if truth in [c["asset_tag"] for c in res.get("candidates", [])]:
        return "fallback_listed"
    if res.get("category") == category_of.get(truth):
        return "fallback_unlisted"          # bon type, mais la machine n'est pas dans la liste proposée
    return "fallback_wrong_category"


def pct(n: int, total: int) -> str:
    return f"{n}/{total} ({100 * n / total:.0f} %)" if total else "-"


# Échauffement : le premier appel charge les modèles (EasyOCR, CLIP) et fausserait les temps
warm = next(iter((ROOT / "data" / "photos").glob("*_noqr.jpg")), None)
if warm:
    identify(warm.read_bytes())

summary, all_results = [], []
for label, folder, pattern in SETS:
    files = sorted(folder.glob(pattern)) if folder.exists() else []
    files = [f for f in files if TAG.search(f.name)]
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f"[ignoré] {label} : aucune image dans {folder}")
        continue
    outcomes, methods, times, bad = Counter(), Counter(), [], []
    for f in files:
        truth = TAG.search(f.name).group(1)
        t0 = time.perf_counter()
        res = identify(f.read_bytes())
        times.append(time.perf_counter() - t0)
        kind = classify(res, truth)
        outcomes[kind] += 1
        methods[res.get("method") or "aucune"] += 1
        if kind in ("silent_error", "confirm_wrong", "read_error", "fallback_wrong_category"):
            bad.append((f.name, kind, res.get("asset_tag"), res.get("method")))
        all_results.append({"set": label, "file": f.name, "truth": truth, "outcome": kind,
                            "predicted": res.get("asset_tag"), "method": res.get("method"),
                            "confidence": res.get("confidence"), "seconds": round(times[-1], 2)})
    summary.append((label, len(files), outcomes, methods, times, bad))

print("\n| Jeu d'images | Identification correcte | Confirmation demandée | Erreur silencieuse |")
print("|---|---|---|---|")
for label, n, o, _, _, _ in summary:
    confirm = o["confirm_ok"] + o["confirm_wrong"]
    print(f"| {label} ({n} images) | {pct(o['direct_ok'], n)} | {pct(confirm, n)} "
          f"dont {o['confirm_ok']} bonne(s) proposition(s) | {pct(o['silent_error'], n)} |")

for label, n, o, methods, times, bad in summary:
    print(f"\n--- {label} ({n} images)")
    print("Issues :", dict(o))
    print("Méthodes :", dict(methods))
    print(f"Temps par image : médiane {statistics.median(times):.1f} s, maximum {max(times):.1f} s")
    fb = o["fallback_listed"] + o["fallback_unlisted"] + o["fallback_wrong_category"]
    if fb:
        print(f"Repli sur le type : {pct(o['fallback_listed'] + o['fallback_unlisted'], fb)} de bon type, "
              f"dont {o['fallback_unlisted']} machine(s) absente(s) de la liste proposée")
    for name, kind, pred, method in bad[:10]:
        print(f"  ! {name} : {kind} (prédit : {pred}, méthode : {method})")

out = ROOT / "eval" / "vision_results.json"
out.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nDétail image par image : {out}")