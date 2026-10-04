import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.nlp.language import normalize_query
from app.rag.retriever import search

# (groupe, question, texte attendu dans un extrait) : recherche SANS filtre de manuel
CASES = [
    ("fr", "Que faire en cas de fuite hydraulique ?", "Code E201"),
    ("fr", "Quelle référence de câble pour une erreur Profinet ?", "RF-CAB-330"),
    ("fr", "Quand remplacer la batterie de sauvegarde du robot ?", "RF-BAT-002"),
    ("fr", "Comment consigner la machine avant intervention ?", "Verrouiller le sectionneur"),
    ("fr", "À quelle fréquence étalonner la visseuse ?", "Étalonnage du couple"),
    ("fr", "Quand nettoyer les atomiseurs ?", "Nettoyage des atomiseurs"),
    ("fr", "Erreur de couple de serrage hors tolérance", "Code E302"),
    ("fr", "Code E101 surchauffe moteur", "Code E101"),
    # références exactes : avantage BM25
    ("ref", "À quoi sert la référence RF-SEN-077 ?", "RF-SEN-077"),
    ("ref", "Où utiliser la pièce RF-VAL-205 ?", "RF-VAL-205"),
    ("ref", "Pièce RF-RED-120", "RF-RED-120"),
    ("ref", "Cartouche RF-GRS-010", "RF-GRS-010"),
    ("ref", "Quel est le code E402 ?", "Code E402"),
    # reformulations sans mots-clés : avantage dense / reranker
    ("para", "La machine s'arrête seule, la porte de sécurité est ouverte", "Code E501"),
    ("para", "Le robot fait un bruit anormal dans un axe", "Code E401"),
    ("para", "L'huile coule sous la presse", "Code E201"),
    ("para", "L'air comprimé est trop faible", "Code E202"),
    ("para", "Le moteur est brûlant", "Code E101"),
    ("para", "On perd le signal de position d'un axe", "Code E102"),
    # darija
    ("darija", "kayn tsrib dyal zit f la presse, achno ndir ?", "Code E201"),
    ("darija", "l moteur skhoun bzaf f robot, achno ndir ?", "Code E101"),
    ("darija", "kayn mochkil f réseau Profinet f l'automate", "Code E301"),
    ("darija", "kifach nconsigni la machine qbel ma nbda l'intervention ?", "Verrouiller le sectionneur"),
    ("darija", "كل شحال خاصني نكريسي المحاور ديال الروبو؟", "Graissage des axes"),
    ("darija", "chhal mn merra khasni ndir l'étalonnage dyal la visseuse ?", "Étalonnage du couple"),
]
MODES = ["dense", "hybrid", "rerank"]
GROUPS = ["fr", "ref", "para", "darija"]
K = 5


def rank_of(docs, expected):
    for i, d in enumerate(docs, 1):
        if expected in d["text"]:
            return i
    return None


queries = []
for group, q, expected in CASES:
    nq = normalize_query(q)
    queries.append((group, nq["french"], expected))
    if group == "darija":
        print(f"{q}\n   -> {nq['french']}")

print("\nhit@1 / hit@3 par groupe, MRR@5 global (recherche sans filtre de manuel)\n")
print("| Mode | " + " | ".join(GROUPS) + " | MRR |")
print("|---|" + "---|" * (len(GROUPS) + 1))
for mode in MODES:
    ranks = {g: [] for g in GROUPS}
    for group, french, expected in queries:
        ranks[group].append(rank_of(search(french, source=None, k=K, mode=mode), expected))
    cells, rr = [], []
    for g in GROUPS:
        r = ranks[g]
        h1 = sum(x == 1 for x in r)
        h3 = sum(x is not None and x <= 3 for x in r)
        cells.append(f"{h1}/{len(r)} · {h3}/{len(r)}")
        rr += [1 / x if x else 0 for x in r]
    print(f"| {mode} | " + " | ".join(cells) + f" | {sum(rr) / len(rr):.2f} |")