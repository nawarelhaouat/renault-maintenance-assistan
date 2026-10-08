import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import auth, dashboard, history
from app.auth import current_user
from app.db import query


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("WARMUP") == "1":                 # précharge les modèles au démarrage
        from app.rag.retriever import search
        search("test", k=1)
    yield


app = FastAPI(title="Assistant Maintenance API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(dashboard.router)


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


@app.get("/machines", dependencies=[Depends(current_user)])
def machines():
    return query("SELECT asset_tag, manufacturer, model_name, category, workshop, line_name, status "
                 "FROM machine_summary ORDER BY asset_tag")


@app.get("/machines/{asset_tag}", dependencies=[Depends(current_user)])
def machine(asset_tag: str):
    rows = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (asset_tag.upper(),))
    if not rows:
        raise HTTPException(status_code=404, detail="Machine introuvable")
    return rows[0]


@app.post("/identify", dependencies=[Depends(current_user)])
def identify_machine(file: UploadFile = File(...)):
    from app.vision.identify import identify
    return identify(file.file.read())


@app.get("/risk/{asset_tag}", dependencies=[Depends(current_user)])
def risk(asset_tag: str):
    from app.ml.predict import risk_report
    return {"asset_tag": asset_tag.upper(), "report": risk_report(asset_tag.upper())}