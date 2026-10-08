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

    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

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
