# -*- coding: utf-8 -*-
"""계정 로그인 — 표준 라이브러리만 사용 (외부 의존성 없음).

- 비밀번호: PBKDF2-HMAC-SHA256 (salt 개별, 20만 회) — bcrypt 미설치
  환경에서도 동작해야 해서 hashlib 로 구현
- 자동 로그인: HMAC 서명 토큰을 쿠키에 저장 (extra_streamlit_components
  가 있으면 사용, 없으면 세션 로그인만)
- 계정 저장: app_settings key='auth_users' (JSON) — 배포 없이 DB 에서
  계정 추가/변경 가능
"""
import hashlib
import hmac
import json
import secrets as _pysecrets
import time

PBKDF2_ITER = 200_000


def hash_pw(pw: str) -> str:
    """새 비밀번호 해시 — 'pbkdf2$반복수$salt$hash'"""
    salt = _pysecrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"),
                             bytes.fromhex(salt), PBKDF2_ITER)
    return f"pbkdf2${PBKDF2_ITER}${salt}${dk.hex()}"


def verify_pw(pw: str, stored: str) -> bool:
    try:
        scheme, iters, salt, hx = (stored or "").split("$")
        if scheme != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", (pw or "").encode("utf-8"),
                                 bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), hx)
    except Exception:
        return False


def make_token(username: str, secret: str, days: int = 14) -> str:
    """자동 로그인 토큰 — 'user|만료시각|서명'"""
    exp = int(time.time()) + days * 86400
    msg = f"{username}|{exp}"
    sig = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"),
                   hashlib.sha256).hexdigest()
    return f"{msg}|{sig}"


def parse_token(token: str, secret: str):
    """유효하면 username, 아니면 None (서명 불일치·만료 포함)"""
    try:
        username, exp, sig = str(token).rsplit("|", 2)
        msg = f"{username}|{exp}"
        good = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"),
                        hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, good) and int(exp) > time.time():
            return username
    except Exception:
        pass
    return None


def load_users(db) -> dict:
    """app_settings.auth_users → {아이디: {name, role, pw}}"""
    try:
        row = db.fetch_one("app_settings", "key=eq.auth_users", "value")
        return json.loads(row["value"]) if row and row.get("value") else {}
    except Exception:
        return {}


def save_users(db, users: dict) -> bool:
    return db.update("app_settings", "key=eq.auth_users",
                     {"value": json.dumps(users, ensure_ascii=False)})


def load_secret(db) -> str:
    try:
        row = db.fetch_one("app_settings", "key=eq.auth_secret", "value")
        return (row or {}).get("value") or ""
    except Exception:
        return ""
