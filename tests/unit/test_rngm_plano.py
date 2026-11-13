"""Helpers del archivo plano RNGM (guía RUNTPRO GM Fase II).

Cubre la sanitización ASCII, los mapeos de catálogo (tipo de
documento, DANE/DIVIPOLA), la partición del nombre completo en los
formatos 'NOMBRES APELLIDOS' (flujo nuevo) y 'APELLIDOS NOMBRES'
(log histórico) y las piezas del nombre de archivo.
"""

import pytest

from backend.services.rngm_plano_service import (
    _ascii,
    _dane_ciudad,
    _nit_sin_dv,
    _nombre_archivo,
    _partir_nombre,
    _telefonos,
    _tipo_doc_runt,
)


class TestAscii:
    def test_quita_tildes_y_sube_mayusculas(self):
        assert _ascii("Londoño Sánchez") == "LONDONO SANCHEZ"
        assert _ascii("Ibagué ñandú") == "IBAGUE NANDU"

    def test_quita_pipes_y_saltos(self):
        assert "|" not in _ascii("CL 1 | 2 - 3\nAP 4")
        assert _ascii("a\rb\nc") == "A B C"

    def test_none_vacio(self):
        assert _ascii(None) == ""
        assert _ascii("  ") == ""

    def test_colapsa_espacios(self):
        assert _ascii("  KR  17   A ") == "KR 17 A"


class TestNitSinDv:
    def test_nit_limpio(self):
        assert _nit_sin_dv("814005081") == "814005081"

    def test_nit_con_dv(self):
        assert _nit_sin_dv("814005081-3") == "814005081"
        assert _nit_sin_dv("814005081 3") == "814005081"

    def test_nit_con_puntos(self):
        assert _nit_sin_dv("814.005.081") == "814005081"


class TestTipoDocRunt:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("1", "C"),
            ("CC", "C"),
            ("Cedula De Ciudadania", "C"),
            ("2", "N"),
            ("NIT", "N"),
            ("4", "E"),
            ("Cedula De Extranjeria", "E"),
            ("5", "P"),
            ("PASAPORTE", "P"),
            ("7", "T"),
            ("Tarjeta De Identidad", "T"),
        ],
    )
    def test_mapeos(self, entrada, esperado):
        assert _tipo_doc_runt(entrada) == esperado

    @pytest.mark.parametrize("entrada", ["3", "PJE", "6", "PPT", "8", "DNI", "9", "PEP", None, ""])
    def test_sin_equivalente(self, entrada):
        assert _tipo_doc_runt(entrada) == ""


class TestTelefonos:
    def test_celular_con_prefijo_57(self):
        assert _telefonos("573207037508") == ("", "3207037508")

    def test_celular_10_digitos(self):
        assert _telefonos("320 703 7508") == ("", "3207037508")

    def test_fijo_7_digitos(self):
        assert _telefonos("6789012") == ("6789012", "")

    def test_fijo_10_digitos_indicativo(self):
        # Fijo nacional: 10 dígitos empezando en 60.
        assert _telefonos("6026789012") == ("6026789012", "")

    def test_vacio(self):
        assert _telefonos(None) == ("", "")
        assert _telefonos("123") == ("", "")


class TestDaneCiudad:
    def test_palmira_valle(self):
        assert _dane_ciudad("Palmira", "Valle del Cauca") == ("76", "76520")

    def test_ibague_tolima(self):
        assert _dane_ciudad("Ibague", "Tolima") == ("73", "73001")

    def test_nombre_unico_sin_departamento(self):
        # Tuluá no se repite en otro departamento: resuelve sin depto.
        assert _dane_ciudad("Tulua", "") == ("76", "76834")

    def test_ciudad_desconocida(self):
        assert _dane_ciudad("Ciudad Inexistente", "Valle del Cauca") == ("", "")

    def test_normaliza_tildes(self):
        assert _dane_ciudad("Ibagué", "Tolima") == ("73", "73001")


class TestPartirNombre:
    def test_nombres_apellidos_con_primer_apellido(self):
        # Flujo nuevo: el formulario pide el primer apellido.
        assert _partir_nombre("NORMA LUCIA PEREZ GOMEZ", "PEREZ", "flujo") == (
            "NORMA",
            "LUCIA",
            "PEREZ",
            "GOMEZ",
        )

    def test_dos_tokens(self):
        assert _partir_nombre("CAROLINA CHINCHA", "CHINCHA", "flujo") == (
            "CAROLINA",
            "",
            "CHINCHA",
            "",
        )

    def test_historico_apellidos_primero(self):
        # Log histórico: 'VELEZ MARQUINEZ INGRID TATIANA' y su
        # primer_apellido quedó con el último token (no es confiable).
        assert _partir_nombre(
            "VELEZ MARQUINEZ INGRID TATIANA", "TATIANA", "cargue_historico"
        ) == ("INGRID", "TATIANA", "VELEZ", "MARQUINEZ")

    def test_historico_tres_tokens(self):
        assert _partir_nombre("SOLANO MENESES KATHERINE", "", "cargue_historico") == (
            "KATHERINE",
            "",
            "SOLANO",
            "MENESES",
        )

    def test_moderno_sin_apellido_confiable(self):
        assert _partir_nombre("JUAN CARLOS RUIZ PAEZ", "", "flujo") == (
            "JUAN",
            "CARLOS",
            "RUIZ",
            "PAEZ",
        )

    def test_un_token(self):
        assert _partir_nombre("CHER", "", "flujo") == ("CHER", "", "", "")

    def test_vacio(self):
        assert _partir_nombre("", "", "flujo") == ("", "", "", "")
        assert _partir_nombre(None, None, "flujo") == ("", "", "", "")


class TestNombreArchivo:
    def test_formato(self):
        import datetime

        assert _nombre_archivo("814005081", 1, datetime.date(2026, 11, 10)) == (
            "814005081RGM00120261110.txt"
        )

    def test_consecutivo_tres_digitos(self):
        import datetime

        assert _nombre_archivo("890903938", 103, datetime.date(2023, 6, 20)) == (
            "890903938RGM10320230620.txt"
        )
