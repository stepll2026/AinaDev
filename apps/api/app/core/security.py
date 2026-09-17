"""安全工具：密码哈希、JWT、AES 加密。"""
import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


# ---------- 密码 ----------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": _utcnow(),
        "exp": _utcnow() + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    return create_token(str(user_id), "access", timedelta(minutes=settings.jwt_access_expire_minutes))


def create_refresh_token(user_id: int) -> str:
    return create_token(str(user_id), "refresh", timedelta(days=settings.jwt_refresh_expire_days))


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != expected_type:
            return None
        return payload
    except jwt.PyJWTError:
        return None


# ---------- AES-256-GCM 加密（模型 API Key 等敏感配置） ----------
def _aes_key_bytes() -> bytes:
    key = settings.aes_key.encode("utf-8")
    if len(key) != 32:
        # 退化为 sha256 派生，保证 32 字节
        digest = hashes.Hash(hashes.SHA256())
        digest.update(key)
        return digest.finalize()
    return key


def aes_encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    key = _aes_key_bytes()
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def aes_decrypt(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        key = _aes_key_bytes()
        raw = base64.b64decode(encrypted)
        nonce, ct = raw[:12], raw[12:]
        return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        return ""
