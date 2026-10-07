"""Autenticación OAuth2 con DataCrédito Experian (Okta y SPLA), con caché de tokens."""

import base64
import threading
import time
from dataclasses import dataclass

import httpx

from backend.config import Settings, get_settings
from backend.services.motor_exceptions import AuthError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.datacredito.auth")

MARGEN_EXPIRACION_SEGUNDOS = 60


@dataclass
class TokenInfo:
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    obtained_at: float = 0.0

    def expirado(self, margen_segundos: int = MARGEN_EXPIRACION_SEGUNDOS) -> bool:
        return time.time() - self.obtained_at >= self.expires_in - margen_segundos


def _token_desde_respuesta(servicio: str, response: httpx.Response, scope_default: str) -> TokenInfo:
    if response.status_code != 200:
        raise AuthError(servicio, response.status_code, response.text[:500])
    try:
        payload = response.json()
        return TokenInfo(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_in=int(payload.get("expires_in", 1800)),
            scope=payload.get("scope", scope_default),
            obtained_at=time.time(),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise AuthError(servicio, response.status_code, "Respuesta de token inválida") from exc


class OktaAuth:
    """Gestiona tokens OAuth2 con caché en memoria segura entre hilos."""

    def __init__(self, settings: Settings | None = None, timeout: float = 30.0):
        self.settings = settings or get_settings()
        self.timeout = timeout
        self._cache: dict[tuple[str, str, str, str], TokenInfo] = {}
        self._lock = threading.Lock()

    def _cacheado(self, clave: tuple[str, str, str, str]) -> TokenInfo | None:
        token = self._cache.get(clave)
        return token if token and not token.expirado() else None

    def get_hdc_spla_token(
        self, username: str, password: str, client_id: str, client_secret: str, token_url: str
    ) -> TokenInfo:
        """Token HDC+ por SPLA (credenciales en JSON)."""
        clave = (token_url, "hdc_spla", client_id, username)
        with self._lock:
            if token := self._cacheado(clave):
                return token
            headers = {
                "client_id": client_id,
                "client_secret": client_secret,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        token_url, headers=headers, json={"username": username, "password": password}
                    )
            except httpx.RequestError as exc:
                raise AuthError("hdc_spla", None, f"Error de red: {exc}") from exc
            token = _token_desde_respuesta("hdc_spla", response, "hdc")
            self._cache[clave] = token
            return token

    def get_token(
        self,
        scope: str,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
        token_url: str | None = None,
    ) -> TokenInfo:
        """Token Okta (grant password). Reutiliza el cacheado si sigue vigente."""
        endpoint = token_url or self.settings.okta_token_url
        clave = (endpoint, scope, client_id, username)
        with self._lock:
            if token := self._cacheado(clave):
                return token
            logger.info("Solicitando nuevo token | scope=%s", scope)
            basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            headers = {
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "accept": "application/json",
            }
            data = {"grant_type": "password", "username": username, "password": password, "scope": scope}
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, headers=headers, data=data)
            except httpx.RequestError as exc:
                raise AuthError("okta", None, f"Error de red: {exc}") from exc
            token = _token_desde_respuesta("okta", response, scope)
            self._cache[clave] = token
            return token


_auth_compartido: OktaAuth | None = None


def get_auth() -> OktaAuth:
    """Instancia compartida para que la caché de tokens sirva entre requests."""
    global _auth_compartido
    if _auth_compartido is None:
        _auth_compartido = OktaAuth()
    return _auth_compartido
