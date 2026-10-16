"""Normalización del teléfono de contacto al formato WhatsApp (WATI)."""

import pytest

from backend.integrations.wati.client import normalizar_telefono_whatsapp


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("3001234567", "573001234567"),  # celular local → antepone 57
        ("300 123 4567", "573001234567"),
        ("+57 300 123 4567", "573001234567"),
        ("573001234567", "573001234567"),
        ("00573001234567", "573001234567"),  # prefijo internacional 00
        ("57-300-123-4567", "573001234567"),
    ],
)
def test_normaliza_a_formato_internacional(entrada, esperado):
    assert normalizar_telefono_whatsapp(entrada) == esperado


@pytest.mark.parametrize("entrada", [None, "", "12345", "   ", "abcd"])
def test_entrada_invalida_devuelve_none(entrada):
    assert normalizar_telefono_whatsapp(entrada) is None
