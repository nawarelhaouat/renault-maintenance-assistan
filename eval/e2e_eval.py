import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.graph import run  # noqa: E402
from app.db import query  # noqa: E402


def first(cat: str) -> str:
    return query("SELECT asset_tag FROM machine_summary WHERE category = %s ORDER BY asset_tag LIMIT 1", (cat,))[0]["asset_tag"]


def has(*subs):
    return lambda a, t: all(s.lower() in a.lower() for s in subs)


def refuses(a, t):
    return "introuvable" in a.lower()


def shows_total(a, t):
    total = query("SELECT total_interventions AS n FROM machine_summary WHERE asset_tag = %s", (t,))[0]["n"]
    return str(total) in a


CASES = [
    ("procédure", "Automate", "Que faire en cas de E301 ?", has("RF-CAB-330", "voyants")),
    ("procédure", "Presse", "Que faire en cas de E201 ?", has("RF-JNT-310")),
    ("symptôme", "Presse", "La presse a une fuite d'huile, que faire ?", has("RF-JNT-310")),
    ("symptôme", "Visseuse", "Le couple de serrage est hors tolérance", has("étalonn")),
    ("préventif", "Robot", "Quand graisser les axes ?", has("90")),
    ("préventif", "Visseuse", "À quelle fréquence étalonner la visseuse ?", has("30")),
    ("darija", "Automate", "kayn mochkil f réseau Profinet, achno ndir ?", has("RF-CAB-330")),
    ("darija", "Presse", "kayn tsrib dyal zit f la presse, achno ndir ?", has("RF-JNT-310")),
    ("darija", "Robot", "l moteur skhoun bzaf, achno ndir ?", has("RF-MOT-210")),
    ("darija (arabe)", "Automate", "كيفاش نصلح مشكل Profinet؟", has("RF-CAB-330")),
    ("refus", "Automate", "Quand graisser ?", refuses),
    ("refus", "Automate", "Quelle est la recette du couscous ?", refuses),
    ("refus", "Visseuse", "Comment changer un pneu de voiture ?", refuses),
    ("SQL", "Automate", "Combien de fois cette machine a eu une maintenance ?", shows_total),
    ("SQL", "Automate", "Quelle est sa dernière panne et comment la résoudre ?", has("Panne E", "Étapes")),
    ("prédiction", "Automate", "Quel est le risque de panne de cette machine ?", has("risque estimé")),
]

tags = {c: first(c) for c in {case[1] for case in CASES}}
by_group, latencies, details = defaultdict(list), [], []
for group, cat, question, check in CASES:
    tag = tags[cat]
    t0 = time.perf_counter()
    try:
        answer, _, _ = run(question, tag, [])
        ok = bool(check(answer, tag))
    except Exception as e:
        answer, ok = f"ERREUR : {type(e).__name__}: {e}", False
    dt = time.perf_counter() - t0
    latencies.append(dt)
    by_group[group].append(ok)
    details.append({"group": group, "machine": tag, "question": question, "ok": ok,
                    "seconds": round(dt, 1), "answer": answer})
    print(f"{'OK ' if ok else 'KO '} [{group}] {question}  ({dt:.1f}s)")

lat = sorted(latencies)
print("\n| Groupe | Réussite |\n|---|---|")
for g, v in by_group.items():
    print(f"| {g} | {sum(v)}/{len(v)} |")
total = sum(sum(v) for v in by_group.values())
print(f"| **Total** | **{total}/{len(CASES)}** |")
print(f"\nLatence : médiane {lat[len(lat) // 2]:.1f}s · p90 {lat[int(len(lat) * 0.9) - 1]:.1f}s · max {lat[-1]:.1f}s")

(ROOT / "eval" / "e2e_results.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
for d in details:
    if not d["ok"]:
        print(f"\n--- ÉCHEC [{d['group']}] {d['question']} ({d['machine']})\n{d['answer'][:400]}")