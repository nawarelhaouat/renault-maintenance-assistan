from app.rag.retriever import tokenize
from app.tools.combined import _strip_common_prefix, build_answer, code_pat

CONTEXT = ("Code E301 : Défaut de communication Profinet Symptôme : Perte de communication. "
           "Étape 1. Vérifier les voyants LINK/ACT du port réseau. "
           "Étape 2. Contrôler le câble Profinet et le remplacer si besoin (réf. RF-CAB-330).")
DOCS = [{"source": "siemens.pdf", "page": 4, "text": CONTEXT}]


def test_invented_step_is_removed_and_citation_is_computed():
    raw = ("1. Vérifier les voyants LINK/ACT du port réseau.\n"
           "2. Contrôler le câble Profinet et le remplacer si besoin (réf. RF-CAB-330).\n"
           "3. Réinitialiser complètement le contrôleur industriel avec un marteau.")
    out = build_answer(raw, CONTEXT, DOCS)
    assert "marteau" not in out
    assert "[siemens.pdf, p.4]" in out
    assert "1 étape(s)" in out
    assert "E301" in out and "LOTO" in out


def test_fully_invented_answer_returns_none():
    raw = "1. Démonter entièrement le châssis et le repeindre en rouge."
    assert build_answer(raw, CONTEXT, DOCS) is None


def test_common_prefix_is_stripped():
    steps = ["Consigner la machine : Arrêter la machine", "Consigner la machine : Verrouiller le sectionneur"]
    assert _strip_common_prefix(steps) == ["Arrêter la machine", "Verrouiller le sectionneur"]
    mixed = ["A : un", "B : deux"]
    assert _strip_common_prefix(mixed) == mixed


def test_code_pattern_tolerates_missing_space_but_not_longer_codes():
    assert code_pat("E501").search("... CodeE501 : Arrêt d'urgence")
    assert code_pat("E501").search("Code E501 : Arrêt d'urgence")
    assert not code_pat("E501").search("Code E5011")


def test_tokenizer_keeps_part_references():
    toks = tokenize("Réf. RF-CAB-330")
    assert "rf-cab-330" in toks and "cab" in toks