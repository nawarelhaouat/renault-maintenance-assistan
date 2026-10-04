import json
import re

import ollama
from app.config import LLM_MODEL

ARABIC = re.compile(r"[\u0600-\u06FF]")
ARABIZI = re.compile(r"\b[3579][a-z]{2,}\b|\b[a-z]{3,}[3579]\b")
MARKERS = {
    "kifach", "kifash", "wach", "achno", "chno", "shno", "kayn", "kayna", "makina", "lmakina",
    "mochkil", "mouchkil", "bzaf", "mzyan", "dyal", "diyal", "dial", "3lach", "imta", "chhal",
    "shhal", "ndir", "khasni", "khasso", "tsrib", "skhoun", "zit", "hadchi", "hadi", "qbel",
}

GLOSSARY = """- makina / ماكينة = machine
- 3tal / عطل = panne
- mochkil / مشكل = problème
- skhoun, tskhen / سخون, تسخن = chaud, surchauffe
- zit / زيت = huile
- tsrib, kaysil / تسريب, كيسيل = fuite
- ma khdamch, ma kat khdem / ما خدامش = ne fonctionne pas
- wqef, twqfat / وقف, توقفات = arrêt, s'est arrêtée
- kifach / كيفاش = comment
- achno ndir / أشنو ندير = que faire
- chhal / شحال = combien
- nkrissi, graissage / نكريسي = graisser
- daghT / ضغط = pression
- hwa / هوا = air comprimé
- khasni / خاصني = je dois
- kayn, kayna / كاين = il y a
- chhal mn merra / شحال من مرة = à quelle fréquence
- qbel / قبل = avant
- visseuse = outil de serrage (jamais "perceuse") ; étalonnage = étalonnage ; presse, robot, automate = inchangés"""

NORMALIZE_PROMPT = f"""Tu es traducteur technique pour la maintenance industrielle d'une usine automobile au Maroc.
L'utilisateur écrit en darija marocain (alphabet arabe ou latin/arabizi, souvent mélangé avec du français).
Reformule sa question en français technique clair. Garde tels quels les codes (E301, TNG-PLC-0001, RF-...).
Ne remplace jamais un terme technique français par un autre (visseuse, presse, robot, automate...).
Glossaire :
{GLOSSARY}
Réponds uniquement en JSON : {{"french": "..."}}"""

TRANSLATE_PROMPT = """Traduis ce texte de maintenance en darija marocain (alphabet arabe).
Garde INCHANGÉS : codes (E101...), références (RF-...), chiffres, noms de fichiers, noms de machines.
Garde la structure (numérotation, listes). Réponds uniquement avec la traduction."""


def detect_language(text: str) -> str:
    """'fr' | 'ar' (alphabet arabe) | 'darija' (arabizi / mots darija en alphabet latin)."""
    if ARABIC.search(text):
        return "ar"
    low = text.lower()
    if set(re.findall(r"[a-z0-9]+", low)) & MARKERS or ARABIZI.search(low):
        return "darija"
    return "fr"


def normalize_query(question: str) -> dict:
    lang = detect_language(question)
    if lang == "fr":
        return {"lang": lang, "original": question, "french": question}
    try:
        r = ollama.chat(
            model=LLM_MODEL, format="json",
            messages=[{"role": "system", "content": NORMALIZE_PROMPT},
                      {"role": "user", "content": question}],
            options={"temperature": 0, "num_ctx": 2048},
        )
        french = json.loads(r["message"]["content"]).get("french", "").strip() or question
    except Exception:
        french = question
    return {"lang": lang, "original": question, "french": french}


def translate_to_darija(text: str) -> str:
    r = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": TRANSLATE_PROMPT}, {"role": "user", "content": text}],
        options={"temperature": 0, "num_ctx": 4096},
    )
    return r["message"]["content"].strip()