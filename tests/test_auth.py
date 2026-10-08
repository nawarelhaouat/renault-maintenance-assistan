import jwt
import pytest

from app.auth import decode_token, hash_password, make_token, verify_password


def test_password_hash_roundtrip_and_random_salt():
    h = hash_password("Secret-2026")
    assert verify_password("Secret-2026", h)
    assert not verify_password("secret-2026", h)
    assert h != hash_password("Secret-2026")


def test_malformed_hash_is_rejected():
    assert not verify_password("x", "pas-un-hash")


def test_token_roundtrip():
    data = decode_token(make_token({"user_id": 7, "username": "nawar", "role": "admin"}))
    assert data["sub"] == "7" and data["role"] == "admin"


def test_garbage_token_is_rejected():
    with pytest.raises(jwt.PyJWTError):
        decode_token("abc.def.ghi")