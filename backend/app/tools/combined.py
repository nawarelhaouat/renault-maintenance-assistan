import re

import ollama
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.config import LLM_MODEL
from app.db import query
from app.rag.retriever import search, tokenize
from app.tools.machine_db import resolve_tag

NOT_FOUND = "Procédure introuvable dans le manuel."
SAFETY_LINE = "**Sécurité** : consigner la machine (LOTO) avant toute intervention."

_RULES = """Recopie MOT POUR MOT TOUTES les étapes de la section concernée, numérotées 1., 2., 3. ...
N'ajoute rien, ne reformule pas, n'invente aucune étape. Pas de citation, pas de titre, pas de consigne de sécurité."""

PROMPT = f"""Tu es un assistant de maintenance industrielle.
Trouve dans les extraits la section qui décrit la panne demandée.
{_RULES}
Format :
1. <étape>
2. <étape>
Si cette section n'est pas dans les extraits, réponds uniquement : {NOT_FOUND}"""

PROMPT_SYMPTOM = f"""Tu es un assistant de maintenance industrielle.
Trouve dans les extraits la section (code d'erreur ou procédure) qui correspond à la question.
Si les extraits décrivent une procédure ou un code d'erreur lié à la question, donne ses étapes,
même si la question est formulée de façon vague.
{_RULES}
Format :
1. <étape>
2. <étape>
Réponds uniquement : {NOT_FOUND} si aucune section des extraits n'a de rapport avec la question."""

STEP_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:étape\s*)?(\d+)[.)]\s+(.*\S)\s*$", re.I)
SECTION_RE = re.compile(r"Code\s*(E\d{3})\s*:\s*(.+?)\s*Sympt[oô]me", re.S)


def code_pat(code: str) -> re.Pattern:
    return re.compile(rf"Code\s*{code}\b")      # tolère "CodeE501" (espace perdu à l'extraction PDF)


def manual_of(tag: str) -> str | None:
    rows = query("SELECT manual_file FROM machine_summary WHERE asset_tag = %s", (tag,))
    return rows[0]["manual_file"] if rows else None


def generate(question: str, docs: list[dict], prompt: str) -> tuple[str, str]:
    context = "\n\n".join(f"[{d['source']}, p.{d['page']}]\n{d['text']}" for d in docs)
    resp = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": prompt},
                  {"role": "user", "content": f"Question : {question}\n\nExtraits :\n{context}"}],
        options={"temperature": 0, "num_ctx": 4096},
    )
    return resp["message"]["content"].strip(), context


def raw_extracts(docs: list[dict], n: int = 2) -> str:
    return ("Je n'ai pas pu formuler une procédure fiable. Extraits les plus proches du manuel :\n\n"
            + "\n\n".join(f"> [{d['source']}, p.{d['page']}] {d['text'][:500]}" for d in docs[:n]))


def _content(text: str) -> set[str]:
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return {t for t in tokenize(text) if len(t) >= 5}


def _cite(step: str, docs: list[dict]) -> str:
    toks = _content(step)
    best = max(docs, key=lambda d: len(toks & _content(d["text"])))
    return f"[{best['source']}, p.{best['page']}]"


def _cause(kept: list[str], context: str) -> str:
    """Code d'erreur dont la section du manuel contient les étapes retenues (calculé, pas généré)."""
    steps = set().union(*[_content(s) for s in kept])
    flat = " ".join(context.split())
    best, best_score = None, 0.0
    for sec in re.split(r"(?=Code\s*E\d{3}\s*:)", flat):
        m = SECTION_RE.match(sec)
        if not m or not steps:
            continue
        score = len(steps & _content(sec)) / len(steps)
        if score > best_score:
            best, best_score = m, score
    if best and best_score >= 0.6:
        return f"**Cause probable** : Code {best.group(1)} : {best.group(2)}"
    return ""


def build_answer(raw: str, context: str, docs: list[dict], safety: bool = True,
                 with_cause: bool = True, threshold: float = 0.75):
    """Garde uniquement les étapes retrouvées dans les extraits ; citations et cause calculées ici."""
    ctx = _content(context)
    kept, dropped = [], 0
    for line in raw.splitlines():
        m = STEP_RE.match(line)
        if not m:
            continue
        step = re.sub(r"\s*\[[^\]]*\]\s*$", "", m.group(2))
        toks = _content(step)
        if not toks or len(toks & ctx) / len(toks) >= threshold:
            kept.append(step)
        else:
            dropped += 1
    if not kept:
        return None

    parts = []
    cause = _cause(kept, context) if with_cause else ""
    if cause:
        parts += [cause, ""]
    parts += ["**Étapes**", ""]
    parts += [f"{i}. {s} {_cite(s, docs)}" for i, s in enumerate(kept, 1)]
    if dropped:
        parts.append(f"\n*{dropped} étape(s) absente(s) du manuel ont été retirée(s).*")
    if safety:
        parts.append("\n" + SAFETY_LINE)
    return "\n".join(parts)


def footer(docs: list[dict], context: str, built: str, code: str | None = None) -> str:
    refs = set(re.findall(r"RF-[A-Z]+-\d+", built))
    if code:
        seg = re.search(rf"Code\s*{code}\s*:.*?(?=Code\s*E\d{{3}}\s*:|$)", context.replace("\n", " "), re.S)
        refs |= set(re.findall(r"RF-[A-Z]+-\d+", seg.group(0) if seg else ""))
    out = ""
    if refs:
        parts = query("SELECT reference, name, stock_qty, unit_cost_mad FROM spare_parts "
                      "WHERE reference = ANY(%s) ORDER BY reference", (sorted(refs),))
        if parts:
            out += "\n\n**Pièces citées dans le manuel (stock GMAO)**\n" + "\n".join(
                f"- {p['reference']} · {p['name']} · stock : {p['stock_qty']} · "
                f"{float(p['unit_cost_mad']):,.0f} MAD".replace(",", " ") for p in parts)
    cited = {int(p) for p in re.findall(r"p\.(\d+)", built)}
    shown = [d for d in docs if d["page"] in cited] or docs
    return out + "\n\n*Sources : " + ", ".join(sorted({f"{d['source']} p.{d['page']}" for d in shown})) + "*"


def answer_from(question: str, docs: list[dict], prompt: str, safety: bool = True,
                code: str | None = None, with_cause: bool = True):
    """Retourne (texte | None, statut) avec statut in {'ok', 'notfound', 'ungrounded'}."""
    raw, context = generate(question, docs, prompt)
    if NOT_FOUND in raw:
        return None, "notfound"
    built = build_answer(raw, context, docs, safety, with_cause)
    if not built:
        return None, "ungrounded"
    return built + footer(docs, context, built, code), "ok"


@tool(return_direct=True)
def diagnose_failure(asset_tag: str = "", failure_code: str = "", config: RunnableConfig = None) -> str:
    """Diagnostic d'une panne : dernière panne de la machine, ou le code d'erreur donné."""
    tag = resolve_tag(asset_tag, config)
    if not tag:
        return "Sélectionne ou identifie d'abord une machine."
    code = failure_code.strip().upper()

    if code:
        rows = query("SELECT code AS failure_code, description AS failure, NULL AS opened_at, "
                     "NULL AS downtime_minutes, NULL AS technician FROM failure_codes WHERE code = %s", (code,))
    else:
        rows = query(
            """SELECT w.failure_code, f.description AS failure, w.opened_at, w.downtime_minutes,
                      t.full_name AS technician
               FROM work_orders w JOIN machines m USING (machine_id)
               JOIN failure_codes f ON f.code = w.failure_code
               LEFT JOIN technicians t ON t.technician_id = w.technician_id
               WHERE m.asset_tag = %s AND w.wo_type = 'corrective'
               ORDER BY w.opened_at DESC LIMIT 1""", (tag,))
    if not rows:
        return "Aucune panne trouvée pour cette machine." if not code else f"Code {code} inconnu."
    last = rows[0]
    code = last["failure_code"]

    stats = query(
        """SELECT COUNT(*) AS n, ROUND(AVG(w.downtime_minutes)) AS avg_min
           FROM work_orders w JOIN machines m USING (machine_id)
           WHERE m.asset_tag = %s AND w.failure_code = %s""", (tag, code))[0]

    head = f"### Panne {code} : {last['failure']}\n"
    if last["opened_at"]:
        head += (f"- Dernière occurrence : {str(last['opened_at'])[:10]} · arrêt {last['downtime_minutes']} min"
                 f" · technicien : {last['technician']}\n")
    head += f"- Sur {tag} : {stats['n']} occurrence(s), arrêt moyen {stats['avg_min'] or 0} min\n"

    source = manual_of(tag)
    pat = code_pat(code)
    docs = search(f"Code {code} {last['failure']} dépannage", source=source, k=8)
    if not any(pat.search(d["text"]) for d in docs):
        return head + f"\nLe code {code} n'est pas décrit dans le manuel de ce modèle ({source})."
    docs.sort(key=lambda d: not pat.search(d["text"]))
    docs = docs[:3]

    out, _ = answer_from(f"Procédure de résolution de la panne {code} : {last['failure']}",
                         docs, PROMPT, True, code, with_cause=False)
    return head + "\n" + (out or NOT_FOUND)