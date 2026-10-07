"""Re-exporta los modelos usados por las pruebas desde un solo lugar."""

from backend.models.buro_models import *  # noqa: F401,F403
from backend.models.motor_models import ResultadoMotor, Solicitud  # noqa: F401
from backend.services.motor_parametros import MotorParametros

# Nombre histórico usado en las pruebas portadas del motor de Juan.
ParametrosIP = MotorParametros
