import os
from contextlib import asynccontextmanager

from app.db import query
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

API_KEY = os.getenv("API_KEY", "")


def auth(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")


class ChatIn(BaseModel):
    question: str
    asset_tag: str | None = None
    history: list[tuple[str, str]] = []


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("WARMUP") == "1":                 # précharge les modèles au démarrage
        from app.rag.retriever import search
        search("test", k=1)
    yield


app = FastAPI(title="Assistant Maintenance API", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Vérifie les dépendances : base, Qdrant, Ollama."""
    status = {}
    try:
        query("SELECT 1 AS ok")
        status["db"] = "ok"
    except Exception as e:
        status["db"] = f"erreur : {type(e).__name__}"
    try:
        from app.config import COLLECTION
        from app.rag.retriever import _client
        status["qdrant"] = "ok" if _client().collection_exists(COLLECTION) else "collection absente"
    except Exception as e:
        status["qdrant"] = f"erreur : {type(e).__name__}"
    try:
        import ollama
        ollama.list()
        status["ollama"] = "ok"
    except Exception as e:
        status["ollama"] = f"erreur : {type(e).__name__}"
    return status


@app.get("/machines", dependencies=[Depends(auth)])
def machines():
    return query("SELECT asset_tag, manufacturer, model_name, category, workshop, line_name, status "
                 "FROM machine_summary ORDER BY asset_tag")


@app.get("/machines/{asset_tag}", dependencies=[Depends(auth)])
def machine(asset_tag: str):
    rows = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (asset_tag.upper(),))
    if not rows:
        raise HTTPException(status_code=404, detail="Machine introuvable")
    return rows[0]


@app.post("/identify", dependencies=[Depends(auth)])
def identify_machine(file: UploadFile = File(...)):
    from app.vision.identify import identify
    return identify(file.file.read())


@app.post("/chat", dependencies=[Depends(auth)])
def chat(body: ChatIn):
    from app.agents.graph import run
    answer, trace, nq = run(body.question, body.asset_tag, body.history)
    return {"answer": answer, "language": nq["lang"], "understood_as": nq["french"],
            "tools": [{"tool": t["tool"], "args": t["args"]} for t in trace]}


@app.get("/risk/{asset_tag}", dependencies=[Depends(auth)])
def risk(asset_tag: str):
    from app.ml.predict import risk_report
    return {"asset_tag": asset_tag.upper(), "report": risk_report(asset_tag.upper())}


@app.get("/fleet/risk", dependencies=[Depends(auth)])
def fleet_risk(limit: int = 20):
    from app.ml.predict import score_fleet
    df, as_of = score_fleet()
    top = df.sort_values("risk", ascending=False).head(limit)
    return {"as_of": str(as_of),
            "machines": top[["asset_tag", "model", "workshop", "risk", "level", "drivers"]].to_dict("records")}