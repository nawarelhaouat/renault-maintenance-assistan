import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
import psycopg2.errors
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.db import execute, query

log = logging.getLogger("auth")
ALGO = "HS256"
JWT_HOURS = int(os.getenv("JWT_HOURS", "12"))
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    log.warning("JWT_SECRET absent : clé temporaire, les sessions sautent à chaque redémarrage")

bearer = HTTPBearer(auto_error=False)
router = APIRouter()
_fails: dict[str, list[float]] = {}
MAX_FAILS, LOCK_SECONDS = 5, 300


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
    except ValueError:
        return False
    return hmac.compare_digest(calc.hex(), digest)


_DUMMY_HASH = hash_password("mot-de-passe-factice")    # temps de réponse identique si l'identifiant n'existe pas


def make_token(user: dict) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS)
    payload = {"sub": str(user["user_id"]), "username": user["username"], "role": user["role"], "exp": exp}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGO])


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if cred is None:
        raise HTTPException(status_code=401, detail="Authentification requise")
    try:
        data = decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Session expirée ou invalide") from None
    rows = query("SELECT user_id, username, full_name, role FROM users WHERE user_id = %s AND is_active",
                 (int(data["sub"]),))
    if not rows:
        raise HTTPException(status_code=401, detail="Compte inconnu ou désactivé")
    return rows[0]


def require_roles(*roles: str):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Droits insuffisants")
        return user
    return dependency


def _check_lock(username: str) -> None:
    now = time.time()
    recent = [t for t in _fails.get(username, []) if now - t < LOCK_SECONDS]
    _fails[username] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessaie dans quelques minutes.")


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


@router.post("/auth/login")
def login(body: LoginIn):
    name = body.username.strip().lower()
    _check_lock(name)
    rows = query("SELECT user_id, username, full_name, role, password_hash FROM users "
                 "WHERE username = %s AND is_active", (name,))
    valid = verify_password(body.password, rows[0]["password_hash"] if rows else _DUMMY_HASH)
    if not rows or not valid:
        _fails.setdefault(name, []).append(time.time())
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect")
    _fails.pop(name, None)
    user = {k: rows[0][k] for k in ("user_id", "username", "full_name", "role")}
    return {"access_token": make_token(user), "token_type": "bearer", "user": user}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return user


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9._-]+$")
    full_name: str = Field(default="", max_length=100)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["operator", "technician", "manager", "admin"]


@router.post("/admin/users", status_code=201)
def create_user(body: UserIn, _admin: dict = Depends(require_roles("admin"))):
    try:
        row = execute("INSERT INTO users(username, full_name, password_hash, role) VALUES (%s, %s, %s, %s) "
                      "RETURNING user_id, username, role",
                      (body.username, body.full_name, hash_password(body.password), body.role))
    except psycopg2.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Identifiant déjà utilisé") from None
    return row[0]