import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from app.core.config import settings

JWT_ISSUER = "alcaldia-cucuta-admin"


@dataclass(frozen=True)
class AdminSessionClaims:
    scope: str
    exp: int
    iat: int
    iss: str


def _encode_segment(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _decode_segment(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _session_secret_bytes() -> bytes:
    return settings.admin_session_secret.encode("utf-8")


def _build_signature(signing_input: str) -> str:
    digest = hmac.new(
        _session_secret_bytes(),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _encode_segment(digest)


def verify_admin_pin(pin: str) -> bool:
    cleaned_pin = (pin or "").strip()
    expected_pin = settings.admin_access_pin.strip()
    return hmac.compare_digest(cleaned_pin, expected_pin)


def get_admin_session_remaining_seconds(claims: AdminSessionClaims) -> int:
    return max(claims.exp - int(time.time()), 0)


def get_admin_session_ttl_seconds() -> int:
    return max(settings.admin_session_ttl_minutes, 1) * 60


def create_admin_session_token() -> tuple[str, int, int]:
    ttl_seconds = get_admin_session_ttl_seconds()
    issued_at = int(time.time())
    expires_at = issued_at + ttl_seconds
    header = {
        "alg": "HS256",
        "typ": "JWT",
    }
    claims = {
        "scope": "admin",
        "iss": JWT_ISSUER,
        "iat": issued_at,
        "exp": expires_at,
    }
    header_segment = _encode_segment(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = _encode_segment(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = _build_signature(signing_input)
    return f"{signing_input}.{signature}", ttl_seconds, expires_at


def _decode_legacy_admin_session_token(token: str) -> AdminSessionClaims:
    try:
        payload_segment, signature = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion administrativa invalida.",
        ) from exc

    expected_signature = _build_signature(payload_segment)
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion administrativa invalida.",
        )

    try:
        payload = json.loads(_decode_segment(payload_segment).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion administrativa invalida.",
        ) from exc

    return AdminSessionClaims(
        scope=str(payload.get("scope") or ""),
        exp=int(payload.get("exp") or 0),
        iat=int(payload.get("iat") or 0),
        iss=str(payload.get("iss") or ""),
    )


def decode_admin_session_token(token: str) -> AdminSessionClaims:
    segments = token.split(".")
    if len(segments) == 2:
        claims = _decode_legacy_admin_session_token(token)
    elif len(segments) == 3:
        header_segment, payload_segment, signature = segments
        expected_signature = _build_signature(f"{header_segment}.{payload_segment}")
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesion administrativa invalida.",
            )

        try:
            header = json.loads(_decode_segment(header_segment).decode("utf-8"))
            payload = json.loads(_decode_segment(payload_segment).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesion administrativa invalida.",
            ) from exc

        if str(header.get("alg") or "") != "HS256" or str(header.get("typ") or "") != "JWT":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesion administrativa invalida.",
            )

        claims = AdminSessionClaims(
            scope=str(payload.get("scope") or ""),
            exp=int(payload.get("exp") or 0),
            iat=int(payload.get("iat") or 0),
            iss=str(payload.get("iss") or ""),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion administrativa invalida.",
        )

    if claims.scope != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion administrativa no tiene permisos suficientes.",
        )

    if claims.iss and claims.iss != JWT_ISSUER:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion administrativa no tiene permisos suficientes.",
        )

    remaining_seconds = get_admin_session_remaining_seconds(claims)
    max_allowed_seconds = get_admin_session_ttl_seconds() + 5

    if remaining_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion administrativa expiro. Vuelve a ingresar tu PIN.",
        )

    if remaining_seconds > max_allowed_seconds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesion administrativa expiro. Vuelve a ingresar tu PIN.",
        )

    return claims


def require_admin_session(
    authorization: str | None = Header(default=None),
) -> AdminSessionClaims:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes autenticarte para usar el panel administrativo.",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El formato de autenticacion administrativa no es valido.",
        )

    return decode_admin_session_token(token.strip())
