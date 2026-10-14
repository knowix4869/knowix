"""Server-side, fail-closed integration for Yoti hosted age verification.

Only a provider-issued OVER 18 result is retained in the current Streamlit
session. Evidence, date of birth, and provider result payloads are not stored.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlencode

import requests

BASE_URL = "https://age.yoti.com"
SESSION_URL = f"{BASE_URL}/api/v1/sessions"
SESSION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ErroVerificacaoIdade(RuntimeError):
    """Safe, user-facing age verification error."""


def obter_configuracao(secrets=None, environ=None) -> dict[str, str]:
    """Return provider settings, preferring an injected env in unit tests."""
    env = environ if environ is not None else os.environ
    try:
        sdk_id = secrets.get("YOTI_AGE_SDK_ID", "") if secrets is not None else ""
        api_key = secrets.get("YOTI_AGE_API_KEY", "") if secrets is not None else ""
        public_url = secrets.get("KNOWIX_PUBLIC_URL", "") if secrets is not None else ""
    except (AttributeError, KeyError, TypeError):
        sdk_id = api_key = public_url = ""
    return {
        "sdk_id": str(sdk_id or env.get("YOTI_AGE_SDK_ID", "")).strip(),
        "api_key": str(api_key or env.get("YOTI_AGE_API_KEY", "")).strip(),
        "public_url": str(public_url or env.get("KNOWIX_PUBLIC_URL", "")).strip().rstrip("/"),
    }


def configuracao_disponivel(config: dict[str, str]) -> bool:
    return bool(config.get("sdk_id") and config.get("api_key") and config.get("public_url"))


def criar_sessao(config: dict[str, str], requester=requests) -> tuple[str, str]:
    """Create an OVER-18 hosted session; return provider session id and URL."""
    if not configuracao_disponivel(config):
        raise ErroVerificacaoIdade("A verificação independente de idade ainda não está configurada.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{14,40}", config["sdk_id"]):
        raise ErroVerificacaoIdade("A configuração de verificação de idade está inválida.")
    if not config["public_url"].startswith("https://"):
        raise ErroVerificacaoIdade("O endereço público precisa usar HTTPS.")

    body = {
        "type": "OVER",
        "ttl": 600,
        "age_estimation": {"allowed": True, "threshold": 18, "level": "PASSIVE", "retry_limit": 1},
        "callback": {"auto": True, "url": config["public_url"]},
        "cancel_url": config["public_url"],
        "synchronous_checks": True,
    }
    try:
        response = requester.post(
            SESSION_URL,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "Yoti-Sdk-Id": config["sdk_id"],
            },
            json=body,
            timeout=(4, 12),
        )
        if response.status_code != 200:
            raise ErroVerificacaoIdade("O provedor não conseguiu iniciar a verificação. Tente novamente.")
        payload = response.json()
        session_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
            raise ErroVerificacaoIdade("O provedor retornou uma sessão inválida.")
    except ErroVerificacaoIdade:
        raise
    except (requests.RequestException, ValueError, TypeError) as erro:
        raise ErroVerificacaoIdade("Não foi possível conectar ao serviço de verificação. Tente novamente.") from erro

    launch_url = f"{BASE_URL}/?{urlencode({'sessionId': session_id, 'sdkId': config['sdk_id']})}"
    return session_id, launch_url


def consultar_sessao(config: dict[str, str], session_id: str, requester=requests) -> dict:
    """Fetch a session result using server-held credentials and validate shape."""
    if not SESSION_ID_RE.fullmatch(str(session_id or "")):
        raise ErroVerificacaoIdade("A sessão de verificação não é válida.")
    if not configuracao_disponivel(config):
        raise ErroVerificacaoIdade("A verificação independente de idade ainda não está configurada.")
    try:
        response = requester.get(
            f"{SESSION_URL}/{session_id}/result",
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
                "Yoti-Sdk-Id": config["sdk_id"],
            },
            timeout=(4, 12),
        )
        if response.status_code != 200:
            raise ErroVerificacaoIdade("Não foi possível confirmar o resultado. Tente novamente.")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ErroVerificacaoIdade("O provedor retornou um resultado inválido.")
        return payload
    except ErroVerificacaoIdade:
        raise
    except (requests.RequestException, ValueError, TypeError) as erro:
        raise ErroVerificacaoIdade("Não foi possível confirmar o resultado. Tente novamente.") from erro


def resultado_aprovado(resultado: dict, session_id: str, sdk_id: str) -> bool:
    """Accept only the exact completed session with a positive OVER-18 result."""
    if not isinstance(resultado, dict):
        return False
    estimativa = resultado.get("age_estimation")
    if not isinstance(estimativa, dict):
        return False
    return (
        resultado.get("id") == session_id
        and resultado.get("sdk_id") == sdk_id
        and str(resultado.get("status", "")).upper() == "COMPLETE"
        and str(resultado.get("type", "")).upper() == "OVER"
        and estimativa.get("allowed") is True
        and str(estimativa.get("threshold", "")) == "18"
    )
