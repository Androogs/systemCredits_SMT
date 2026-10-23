"""Cliente Twilio y ruteo del OTP por SMS en NotificacionService."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.config import Settings
from backend.integrations.twilio.client import (
    TwilioClient,
    TwilioError,
    normalizar_telefono_e164,
)
from backend.services.notificacion_service import NotificacionService


def _settings(**kw) -> Settings:
    base = dict(
        twilio_account_sid="ACtest",
        twilio_auth_token="tok",
        twilio_from_number="+15005550006",
        # Vacío para que el test nunca llame a WATI/SMTP reales.
        wati_base_url="",
        wati_tenant_id="",
        wati_api_token="",
        smtp_host="",
        smtp_desde="",
    )
    base.update(kw)
    return Settings(**base)


def _solicitud(telefono="3001234567"):
    return SimpleNamespace(
        contacto_vivienda=SimpleNamespace(telefono=telefono, correo=None),
        cliente=SimpleNamespace(nombre_completo="Ana Prueba"),
        num_solicitud=42,
    )


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("3001234567", "+573001234567"),
        ("+57 300 123 4567", "+573001234567"),
        ("573001234567", "+573001234567"),
    ],
)
def test_normaliza_a_e164(entrada, esperado):
    assert normalizar_telefono_e164(entrada) == esperado


def test_e164_invalido_devuelve_none():
    assert normalizar_telefono_e164("12345") is None
    assert normalizar_telefono_e164(None) is None


def test_configurado_requiere_sid_token_y_origen():
    assert TwilioClient(_settings()).configurado
    assert not TwilioClient(_settings(twilio_auth_token="")).configurado
    assert not TwilioClient(
        _settings(twilio_from_number="", twilio_messaging_service_sid="")
    ).configurado


def test_enviar_sms_usa_from_number():
    cliente = TwilioClient(_settings())
    with patch.object(cliente, "_post", return_value={"sid": "SM1"}) as post:
        assert cliente.enviar_sms("+573001234567", "hola") == "SM1"
        data = post.call_args.args[1]
        assert data["To"] == "+573001234567"
        assert data["From"] == "+15005550006"
        assert data["Body"] == "hola"


def test_enviar_sms_prefiere_messaging_service():
    cliente = TwilioClient(_settings(twilio_messaging_service_sid="MG1"))
    with patch.object(cliente, "_post", return_value={"sid": "SM2"}) as post:
        cliente.enviar_sms("+573001234567", "hola")
        assert post.call_args.args[1]["MessagingServiceSid"] == "MG1"
        assert "From" not in post.call_args.args[1]


def _servicio(settings: Settings) -> NotificacionService:
    with patch(
        "backend.services.notificacion_service.get_settings",
        return_value=settings,
    ):
        return NotificacionService()


def test_otp_sale_por_sms_cuando_twilio_configurado():
    servicio = _servicio(_settings())
    servicio._twilio.enviar_sms = MagicMock(return_value="SM9")
    envio = servicio.notificar(
        "otp",
        _solicitud(),
        datos={"codigo": "123456", "minutos": 10},
        canal="whatsapp",
    )
    assert envio["canal"] == "sms"
    assert envio["estado"] == "enviado"
    assert envio["destino"] == "+573001234567"
    cuerpo = servicio._twilio.enviar_sms.call_args.args[1]
    assert "123456" in cuerpo


def test_otp_cae_a_email_si_twilio_falla():
    servicio = _servicio(_settings())
    servicio._twilio.enviar_sms = MagicMock(side_effect=TwilioError("down"))
    envio = servicio.notificar(
        "otp",
        _solicitud(),
        datos={"codigo": "123456", "minutos": 10},
        canal="sms",
    )
    assert envio["canal"] == "email"


def test_sin_twilio_whatsapp_sigue_funcionando():
    servicio = _servicio(_settings(twilio_account_sid="", twilio_from_number=""))
    envio = servicio.notificar(
        "otp",
        _solicitud(),
        datos={"codigo": "123456", "minutos": 10},
        canal="whatsapp",
    )
    # Sin Twilio ni WATI reales: WATI no configurado reporta 'simulado'.
    assert envio["canal"] == "whatsapp"
    assert envio["estado"] == "simulado"
