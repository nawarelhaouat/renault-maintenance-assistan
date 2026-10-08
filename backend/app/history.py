import logging

from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import Json
from pydantic import BaseModel, Field

from app.auth import current_user
from app.db import execute, query

router = APIRouter()
log = logging.getLogger("assistant")


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    asset_tag: str | None = None
    conversation_id: int | None = None


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


def _owned(conversation_id: int, user: dict) -> dict:
    rows = query("SELECT conversation_id, title, asset_tag FROM conversations "
                 "WHERE conversation_id = %s AND user_id = %s", (conversation_id, user["user_id"]))
    if not rows:
        raise HTTPException(status_code=404, detail="Discussion introuvable")
    return rows[0]


@router.get("/conversations")
def list_conversations(user: dict = Depends(current_user)):
    return query("SELECT conversation_id AS id, title, asset_tag, updated_at FROM conversations "
                 "WHERE user_id = %s ORDER BY updated_at DESC LIMIT 200", (user["user_id"],))


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, user: dict = Depends(current_user)):
    conv = _owned(conversation_id, user)
    messages = query("SELECT message_id AS id, role, content, asset_tag, meta, created_at FROM messages "
                     "WHERE conversation_id = %s ORDER BY message_id", (conversation_id,))
    return {"conversation": {"id": conv["conversation_id"], "title": conv["title"],
                             "asset_tag": conv["asset_tag"]}, "messages": messages}


@router.patch("/conversations/{conversation_id}")
def rename_conversation(conversation_id: int, body: RenameIn, user: dict = Depends(current_user)):
    _owned(conversation_id, user)
    execute("UPDATE conversations SET title = %s WHERE conversation_id = %s", (body.title.strip(), conversation_id))
    return {"id": conversation_id, "title": body.title.strip()}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, user: dict = Depends(current_user)):
    _owned(conversation_id, user)
    execute("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))


@router.post("/chat")
def chat(body: ChatIn, user: dict = Depends(current_user)):
    if body.asset_tag and not query("SELECT 1 AS ok FROM machines WHERE asset_tag = %s", (body.asset_tag,)):
        raise HTTPException(status_code=404, detail="Machine introuvable")

    if body.conversation_id:
        conv = _owned(body.conversation_id, user)
        cid, title = conv["conversation_id"], conv["title"]
    else:
        title = " ".join(body.question.split())[:60]
        cid = execute("INSERT INTO conversations(user_id, title, asset_tag) VALUES (%s, %s, %s) "
                      "RETURNING conversation_id", (user["user_id"], title, body.asset_tag))[0]["conversation_id"]

    past = query("SELECT role, content FROM messages WHERE conversation_id = %s "
                 "ORDER BY message_id DESC LIMIT 4", (cid,))[::-1]
    history = [(m["role"], m["content"]) for m in past]
    execute("INSERT INTO messages(conversation_id, role, content, asset_tag) VALUES (%s, 'user', %s, %s)",
            (cid, body.question, body.asset_tag))

    from app.agents.graph import run
    try:
        answer, trace, nq = run(body.question, body.asset_tag, history)
    except Exception:
        log.exception("Échec de l'assistant")
        raise HTTPException(status_code=500, detail="L'assistant n'a pas pu répondre. Réessaie dans un instant.") from None

    meta = {"language": nq["lang"], "understood_as": nq["french"] if nq["lang"] != "fr" else None,
            "tools": [t["tool"] for t in trace]}
    row = execute("INSERT INTO messages(conversation_id, role, content, asset_tag, meta) "
                  "VALUES (%s, 'assistant', %s, %s, %s) RETURNING message_id, created_at",
                  (cid, answer, body.asset_tag, Json(meta)))[0]
    execute("UPDATE conversations SET updated_at = now(), asset_tag = %s WHERE conversation_id = %s",
            (body.asset_tag, cid))
    return {"conversation_id": cid, "title": title,
            "answer": {"id": row["message_id"], "role": "assistant", "content": answer,
                       "asset_tag": body.asset_tag, "meta": meta, "created_at": row["created_at"]}}