"""Textos legales versionados (Habeas Data, Ley 1581 de 2012).

El texto que el cliente acepta queda versionado aquí: si el contenido
legal cambia, se crea una versión nueva (v2, v3…) sin tocar la anterior,
así cada consentimiento persistido puede demostrar exactamente qué texto
aceptó el cliente (version_texto + hash_texto = sha256 del cuerpo).

El texto de v1 replica lo que el asesor muestra en pantalla en el paso 2
de originación (AutorizacionDatos) más la referencia al documento
descargable de autorización a centrales de riesgo.
"""

import hashlib

VERSION_HABEAS_DATA = "v1"

TEXTO_HABEAS_DATA_V1 = (
    "AUTORIZACIÓN INFORMADA HABEAS DATA — TRATAMIENTO DE DATOS PERSONALES\n"
    "\n"
    "1. FINALIDAD DEL TRATAMIENTO\n"
    "Análisis de perfil de riesgo de crédito, estructuración del cupo "
    "financiero, prevención de lavado de activos (SARLAFT) y reportes de "
    "comportamiento de pago.\n"
    "\n"
    "2. CONSULTA Y ALMACENAMIENTO\n"
    "Consultar e informar a centrales de riesgo autorizadas legalmente en "
    "el territorio nacional. Los datos se almacenarán por el tiempo "
    "estipulado en la ley colombiana.\n"
    "\n"
    "El cliente autoriza los canales de contacto registrados (celular y "
    "correo electrónico) para recibir notificaciones del proceso "
    "(resultado, oferta y desembolso) y el código de firma del pagaré. "
    "Documento de referencia: autorizacion-consulta-centrales-habeas-data."
)

_TEXTOS = {VERSION_HABEAS_DATA: TEXTO_HABEAS_DATA_V1}


def texto_habeas(version: str = VERSION_HABEAS_DATA) -> str:
    return _TEXTOS[version]


def hash_habeas(version: str = VERSION_HABEAS_DATA) -> str:
    return hashlib.sha256(_TEXTOS[version].encode("utf-8")).hexdigest()
