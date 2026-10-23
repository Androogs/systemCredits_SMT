"""Configuración central (variables de entorno / archivo .env)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # .env anclado a la raíz del proyecto, aunque uvicorn se inicie
        # desde otra carpeta.
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["demo", "produccion"] = "demo"
    log_level: str = "INFO"
    version: str = "1.0.0"

    # --- API / frontend ---
    app_title: str = "Creditos API - Inversiones Pacifico"
    app_version: str = "1.0.0"
    cors_origins: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # URL pública del frontend: es lo que codifica el QR de verificación
    # de firma en los documentos de legalización.
    app_url_publica: str = "http://localhost:5173"
    demo_user_email: str = "demo@underwriting.io"
    demo_user_password: str = "demo1234"

    # --- Autenticación JWT de la plataforma ---
    # Secreto de firma HS256. Obligatorio fuera del entorno demo: sin él
    # el login responde 503 (fail-closed, no se emiten tokens). En demo
    # cae a un valor de desarrollo documentado.
    jwt_secreto: str = ""
    # Vigencia del token: una jornada laboral (decisión del usuario).
    jwt_ttl_horas: int = 8
    # Lockout de login: N fallos seguidos → bloqueo temporal.
    auth_max_intentos: int = 5
    auth_bloqueo_minutos: int = 15
    # Sesión con refresh token (D125): el access JWT sigue siendo corto;
    # el refresh persiste la sesión y se rota en cada uso.
    refresh_token_dias: int = 30
    # Token de "olvidé mi clave" (D124): un solo uso, ventana corta.
    recuperacion_token_minutos: int = 30
    # Roles con acceso al panel (cliente/contabilidad quedan fuera).
    # El orden es la prioridad cuando el usuario acumula roles: un
    # concesionario que también radica conserva la vista de su sede.
    auth_roles_panel: str = "admin,concesionario,asesor,aliado"

    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    def jwt_secreto_efectivo(self) -> str:
        """Secreto real usado para firmar: en demo hay un valor de
        desarrollo para no exigir .env; en producción vacío = sin auth."""
        if self.jwt_secreto:
            return self.jwt_secreto
        if self.environment == "demo":
            return "dev-jwt-secreto-solo-demo-32bytes!"
        return ""

    def roles_panel_list(self) -> list[str]:
        return [r.strip() for r in self.auth_roles_panel.split(",") if r.strip()]

    # --- Motor ---
    # SMMLV vigente en COP. Cambia cada año: actualizar en .env.
    smmlv: int = Field(1_750_905, gt=0)
    parametros_path: Path = RAIZ_PROYECTO / "parametros.json"

    # --- Base de datos ---
    # PostgreSQL (esquema SUMOTO):  postgresql+psycopg://user:pass@host:5432/db
    # Desarrollo / pruebas:         sqlite:///./motor_decision.db
    database_url: str = f"sqlite:///{RAIZ_PROYECTO / 'motor_decision.db'}"
    # Crea las tablas que falten al iniciar. En producción con
    # schema.sql + alembic, dejar en false.
    db_crear_tablas: bool = False

    def sqlalchemy_database_url(self) -> str:
        database_url = self.database_url
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgresql://"):
            return database_url.replace(
                "postgresql://",
                "postgresql+psycopg://",
                1,
            )
        return database_url

    # --- DataCrédito Experian: OAuth ---
    okta_token_url_demo: str = ""
    okta_token_url_prod: str = ""
    # HDC+ UAT usa SPLA; Valor Ingreso usa Okta.
    hdc_token_url_demo: str = ""
    hdc_token_url_prod: str = ""
    income_token_url_demo: str = ""
    income_token_url_prod: str = ""

    # --- Valor Ingreso ---
    income_username: str = ""
    income_password: str = ""
    income_client_id: str = ""
    income_client_secret: str = ""
    income_scope: str = "expco_incomes"
    income_base_url_demo: str = ""
    income_base_url_prod: str = ""
    income_subscriber_name: str = ""

    # --- Historia de Crédito+ ---
    hdc_username: str = ""
    hdc_password: str = ""
    # Credenciales del token SPLA (distintas de las del servicio HDC).
    hdc_token_username: str = ""
    hdc_token_password: str = ""
    hdc_client_id: str = ""
    hdc_client_secret: str = ""
    hdc_base_url_demo: str = ""
    hdc_base_url_prod: str = ""
    hdc_product_id: str = "64"
    server_ip_address: str = ""

    timeout_experian_segundos: float = 60.0
    # --- Rate limiting ---
    rate_limit_habilitado: bool = True
    rate_limit_max_peticiones: int = 30  # métodos mutadores por IP
    rate_limit_ventana_seg: float = 60.0
    # --- Notificaciones al cliente (email SMTP) ---
    # Sin SMTP configurado, el servicio solo registra el envío en log
    # (modo demo: la notificación se muestra en la UI del asesor).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_desde: str = ""
    smtp_tls: bool = True
    # --- Notificaciones al cliente (WhatsApp vía WATI) ---
    # Sin credenciales el envío queda 'simulado' en log, igual que SMTP.
    # El OTP se envía como plantilla de autenticación aprobada por Meta.
    wati_base_url: str = ""  # ej: https://live-mt-server.wati.io
    wati_tenant_id: str = ""
    wati_api_token: str = ""
    # Número WABA del tenant; solo necesario en tenants multi-WABA.
    wati_channel_number: str = ""
    # Nombre de la plantilla de autenticación aprobada para el OTP.
    wati_plantilla_otp: str = "otp_verificacion"
    wati_timeout_segundos: float = 15.0
    # --- Twilio (OTP por SMS via Verify API + mensajes directos) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_verify_sid: str = ""  # VAxxxx del servicio Verify
    twilio_from_number: str = ""  # +57... para SMS directos
    twilio_messaging_service_sid: str = ""  # MGxxxx alternativo
    twilio_timeout_segundos: float = 15.0
    # --- OTP ---
    otp_ttl_minutos: int = 10
    otp_max_intentos: int = 3

    # --- Ofertas ---
    oferta_vigencia_dias: int = 15

    # --- Documentos de legalización (paquete de firma) ---
    # Plantillas DOCX con MERGEFIELDs; la firma (OTP) los genera llenos.
    documentos_plantillas_dir: str = str(
        RAIZ_PROYECTO / "backend" / "documentos" / "plantillas"
    )
    # Ciudad donde se firma el paquete (sede del concesionario que radica).
    documentos_ciudad_firma: str = "PALMIRA"
    # Día de pago pactado para la primera cuota del pagaré (como el 20
    # del formato real): la primera cuota cae ese día del mes siguiente
    # a la firma.
    documentos_dia_pago: int = Field(20, ge=1, le=28)

    # --- Captura remota de evidencias ---
    evidencias_dir: str = "uploads/evidencias"  # storage local del MVP; S3 en producción
    captura_ttl_minutos: int = 30  # vigencia del link con token
    evidencia_max_mb: int = 25  # límite por archivo (videos)
    # --- OCR de la cédula (Tesseract) ---
    # Ruta al binario si no está en el PATH (ej. Windows sin PATH configurado).
    tesseract_cmd: str = ""
    # Carpeta con los .traineddata cuando no están junto al binario
    # (ej. Windows sin permisos para escribir en Program Files).
    tessdata_dir: str = ""
    # Idioma(s) del OCR; debe incluir 'spa' (paquete de idioma instalado).
    tesseract_lang: str = "spa"
    # --- Pre-filtro SIMIT (deuda de tránsito) ---
    # Corre antes de consumir la consulta de buró: con deuda pendiente
    # la evaluación rechaza (R22) sin gastar la llamada a Experian.
    # Proveedor: "placapi" (hoy). Cuando el convenio de consulta
    # masiva con la FCM entregue el servicio oficial se agrega "fcm".
    simit_habilitado: bool = True
    simit_proveedor: str = "placapi"
    simit_base_url: str = "https://placapi.com"
    simit_api_key: str = ""
    simit_timeout_segundos: float = 15.0
    # Si SIMIT no responde: False (default) = fail-open, la evaluación
    # sigue sin el pre-filtro; True = la evaluación se bloquea.
    simit_requerido: bool = False

    # --- Reuso de consulta a centrales (tabla consulta_buro) ---
    # La consulta a Experian es un recurso pago por persona: si hay un
    # reporte vigente para (tipo_id, numero_id) la evaluación corre el
    # motor con esos datos en vez de pagar otra llamada. El motor siempre
    # re-corre con los parámetros vigentes — se reusan los datos de
    # centrales, no la decisión. Cada reevaluación con caché queda
    # trazada en auditoría como origen_datos 'cache:experian'.
    buro_cache_habilitado: bool = True
    # Días de vigencia del reporte guardado. 0 = cada evaluación
    # consulta en línea (equivale a apagar el reuso).
    buro_cache_dias: int = 30

    # --- Webhook de confirmación asíncrona (aliados/tesorería) ---
    # Secreto compartido HMAC-SHA256 del emisor. Vacío = endpoint
    # deshabilitado (503): sin secreto configurado no se acepta nada.
    webhook_secreto: str = ""
    # Tolerancia de X-Timestamp en segundos (anti-replay).
    webhook_ventana_segundos: int = 300

    # --- Tasas de mercado SFC (TIBC, datos.gov.co) ---
    # Referencia oficial del Interés Bancario Corriente para precargar
    # la tasa del simulador. Dataset público: no requiere credenciales.
    sfc_tasas_base_url: str = "https://www.datos.gov.co"
    sfc_tasas_timeout_segundos: float = 10.0
    # El dataset se certifica una vez al mes; 6h sobra de refresco.
    sfc_tasas_cache_segundos: float = 21_600.0

    # --- Resiliencia Experian ---
    experian_reintentos: int = 2  # reintentos extra tras el primer intento
    experian_espera_reintento_seg: float = 1.0  # backoff base (x2 por intento)
    experian_circuito_fallos: int = 5  # fallos consecutivos que abren el circuito
    experian_circuito_espera_seg: float = 60.0  # tiempo que el circuito queda abierto

    def _por_ambiente(self, demo: str, prod: str) -> str:
        return demo if self.environment == "demo" else prod

    @property
    def okta_token_url(self) -> str:
        return self._por_ambiente(self.okta_token_url_demo, self.okta_token_url_prod)

    @property
    def hdc_token_url(self) -> str:
        return self._por_ambiente(self.hdc_token_url_demo, self.hdc_token_url_prod) or self.okta_token_url

    @property
    def income_token_url(self) -> str:
        return self._por_ambiente(self.income_token_url_demo, self.income_token_url_prod) or self.okta_token_url

    @property
    def hdc_base_url(self) -> str:
        return self._por_ambiente(self.hdc_base_url_demo, self.hdc_base_url_prod)

    @property
    def income_base_url(self) -> str:
        return self._por_ambiente(self.income_base_url_demo, self.income_base_url_prod)

    def configuracion_experian_faltante(self) -> list[str]:
        """Nombres de variables obligatorias para consultar Experian que están vacías."""
        requeridas = {
            "HDC_USERNAME": self.hdc_username,
            "HDC_PASSWORD": self.hdc_password,
            "HDC_TOKEN_USERNAME": self.hdc_token_username,
            "HDC_TOKEN_PASSWORD": self.hdc_token_password,
            "HDC_CLIENT_ID": self.hdc_client_id,
            "HDC_CLIENT_SECRET": self.hdc_client_secret,
            f"HDC_BASE_URL_{'DEMO' if self.environment == 'demo' else 'PROD'}": self.hdc_base_url,
            "HDC_TOKEN_URL": self.hdc_token_url,
            "SERVER_IP_ADDRESS": self.server_ip_address,
            "INCOME_USERNAME": self.income_username,
            "INCOME_PASSWORD": self.income_password,
            "INCOME_CLIENT_ID": self.income_client_id,
            "INCOME_CLIENT_SECRET": self.income_client_secret,
            "INCOME_SUBSCRIBER_NAME": self.income_subscriber_name,
            f"INCOME_BASE_URL_{'DEMO' if self.environment == 'demo' else 'PROD'}": self.income_base_url,
            "INCOME_TOKEN_URL": self.income_token_url,
        }
        return [nombre for nombre, valor in requeridas.items() if not valor]


@lru_cache
def get_settings() -> Settings:
    return Settings()

