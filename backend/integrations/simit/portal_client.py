"""Proveedor SIMIT por el portal ciudadano público (fcm.org.co/simit).

Flujo descubierto del frontend Quipux del portal (config.js +
captcha-worker.js de qxcaptcha.fcm.org.co):

1. POST https://qxcaptcha.fcm.org.co/api.php (form `endpoint=question`)
   → {"data": {"question": "<hex>", "recommended_difficulty": N}}.
   Gratis e ilimitado.
2. Proof-of-work "WeHateCaptchas": buscar nonce primo tal que
   sha256('{"question":"<q>","time":<ts>,"nonce":<n>}') empiece con
   "0000". ~1-3 s de CPU local, sin OCR ni servicios externos.
3. POST /simit/microservices/estado-cuenta-simit/estadocuenta/consulta
   en consultasimit.fcm.org.co con
   {"filtro": <doc>, "reCaptchaDTO": {"response": "<json del paso 2>",
   "consumidor": "1"}} → estado de cuenta completo.

Advertencias de producción: es la API interna del portal público, sin
SLA (un cambio de endpoint, payload o captcha rompe la integración
hasta re-armarla). Además el flag `pazSalvo` de la respuesta NO es
confiable (se observó `true` con multas pendientes): `paz_y_salvo`
siempre se deriva de totalGeneral y del conteo de ítems. El convenio
oficial FCM (Resolución 35 de 2016) o PlacApi quedan como proveedores
alternos detrás del mismo contrato (ClienteSimit).
"""

import hashlib
import json
import time
from decimal import Decimal
from typing import Any

import httpx

from backend.config import Settings, get_settings
from backend.integrations.datacredito.resiliencia import llamar_con_resiliencia
from backend.integrations.simit.client import ResultadoSimit
from backend.models.enums import TipoIdentificacion
from backend.services.motor_exceptions import DataCreditoError
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.simit.portal")

_SERVICIO = "simit_portal_estado_cuenta"
_MODULO = "/simit/microservices/estado-cuenta-simit/estadocuenta"

# Techo del proof-of-work: la esperanza es ~850k iteraciones; 8M es
# ~10 sigmas — si no resolvió, la pregunta cambió de formato y repetir
# con una nueva no arregla nada.
_POW_MAX_ITER = 8_000_000


def _es_primo(n: int) -> bool:
    if n <= 1:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _resolver_pow(question: str, ts: int) -> int:
    """Nonce primo cuyo JSON compacto hashea con prefijo "0000".

    Replica de solveCaptcha() de captcha-worker.js: el worker arma
    JSON.stringify({question, time, nonce}) — sin espacios — y exige
    sha256(...)[:4] == "0000" y nonce primo.
    """
    nonce = 1
    for _ in range(_POW_MAX_ITER):
        nonce += 1
        payload = f'{{"question":"{question}","time":{ts},"nonce":{nonce}}}'
        if hashlib.sha256(payload.encode()).hexdigest().startswith(
            "0000"
        ) and _es_primo(nonce):
            return nonce
    raise DataCreditoError(
        _SERVICIO, None, "PoW captcha sin solución en el techo de iteraciones"
    )


def _items_lista(bloque: Any) -> int:
    return len(bloque) if isinstance(bloque, list) else 0


class PortalSimitClient:
    """Scraper del portal ciudadano SIMIT: PoW captcha → consulta."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base = (
            self.settings.simit_portal_base_url.rstrip("/") + _MODULO
        )

    def _request(
        self,
        http: httpx.Client,
        metodo: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        def llamada() -> httpx.Response:
            try:
                resp = http.request(metodo, url, **kwargs)
            except httpx.RequestError as exc:
                raise DataCreditoError(
                    _SERVICIO, None, f"Error de red: {exc}"
                ) from exc
            if resp.status_code != 200:
                raise DataCreditoError(
                    _SERVICIO, resp.status_code, resp.text[:500]
                )
            return resp

        return llamar_con_resiliencia(_SERVICIO, self.settings, llamada)

    def _nueva_verificacion(self, http: httpx.Client) -> str:
        """Pregunta PoW resuelta, serializada como la espera el portal:
        '[{"question":"…","time":…,"nonce":…}]' (un ítem basta)."""
        resp = self._request(
            http,
            "POST",
            self.settings.simit_portal_captcha_url,
            data={"endpoint": "question"},
        )
        try:
            question = str(resp.json()["data"]["question"])
        except (ValueError, KeyError, TypeError) as exc:
            raise DataCreditoError(
                _SERVICIO, resp.status_code, f"captcha api.php inesperado: {exc}"
            ) from exc
        ts = int(time.time())
        nonce = _resolver_pow(question, ts)
        return json.dumps(
            [{"question": question, "time": ts, "nonce": nonce}],
            separators=(",", ":"),
        )

    def estado_cuenta_transito(
        self,
        tipo_id: TipoIdentificacion,
        numero_id: str,
    ) -> ResultadoSimit:
        """Deuda SIMIT de la persona por documento.

        El `filtro` del portal acepta documento o placa en el mismo
        campo — el backend distingue el tipo solo. Con deuda pendiente
        el portal igual puede responder `pazSalvo: true`, por eso el
        resultado se deriva del total y del conteo, no del flag.
        """
        with httpx.Client(
            timeout=self.settings.simit_timeout_segundos, verify=True
        ) as http:
            verificacion = self._nueva_verificacion(http)
            body = {
                "filtro": numero_id,
                "reCaptchaDTO": {
                    "response": verificacion,
                    "consumidor": "1",
                },
            }
            resp = self._request(
                http, "POST", self.base + "/consulta", json=body
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise DataCreditoError(
                _SERVICIO, resp.status_code, f"JSON inválido: {exc}"
            ) from exc
        if not isinstance(data, dict) or "totalGeneral" not in data:
            raise DataCreditoError(
                _SERVICIO,
                resp.status_code,
                f"/consulta inesperado: {str(data)[:300]}",
            )

        items = sum(
            _items_lista(data.get(k))
            for k in ("multas", "resoluciones", "comparendos", "acuerdosPago")
        )
        try:
            deuda = Decimal(str(data.get("totalGeneral") or 0))
        except ValueError:
            deuda = Decimal(0)
        paz_salvo = deuda == 0 and items == 0
        logger.info(
            "SIMIT portal %s/%s | paz_salvo=%s deuda=%s items=%s",
            tipo_id.name,
            numero_id,
            paz_salvo,
            deuda,
            items,
        )
        return ResultadoSimit(
            paz_y_salvo=paz_salvo,
            total_deuda=deuda,
            total_items=items,
            origen="portal",
        )
