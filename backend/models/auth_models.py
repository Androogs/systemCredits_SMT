"""Esquemas de autenticación de la API."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    correo: str = Field(min_length=3, max_length=254)
    contrasena: str = Field(min_length=1, max_length=256)


class UsuarioAutenticado(BaseModel):
    correo: str
    nombre: str
    rol: str


class LoginResponse(BaseModel):
    usuario: UsuarioAutenticado
