"""OCR de la cédula de ciudadanía colombiana (paso 3 del wizard).

El cliente sube desde su celular la foto del anverso y del reverso (ver
``EvidenciaService``). Cada foto se analiza por separado y el resultado de
ambas caras se FUSIONA, sin importar el orden en que lleguen:

- **Cédula blanca (digital)**: el reverso trae el MRZ con dígitos de control;
  si validan, manda para número, nombres, nacimiento, sexo y expiración. El
  anverso aporta lugar de nacimiento y fecha/ciudad de expedición.
- **Cédula amarilla**: el anverso trae número, apellidos y nombres; el reverso
  trae nacimiento, lugar, sexo y expedición, y una línea al pie con sexo y
  número que sirve para cruzar con el anverso.

El tipo de cédula y la cara se detectan por el CONTENIDO de la foto, no por el
botón que usó el cliente: si sube el reverso como anverso, igual se lee bien
(y queda una observación).

El OCR es *best-effort*: nunca bloquea la subida ni el flujo. Las diferencias
contra lo digitado por el asesor (o entre anverso y reverso) generan
advertencias; el asesor confirma los datos en la revisión.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from backend.config import get_settings
from backend.services import ocr_imagen as img
from backend.services.ocr_parser import (
    CAMPOS,
    CAMPOS_POR_CARA,
    CARA_FRONTAL,
    CARA_REVERSO,
    TIPO_BLANCA,
    LecturaParseada,
    Votacion,
    clasificar,
    parsear_lineas,
    plano_ascii,
)
from backend.utils.loggers import get_logger

logger = get_logger("creditos.ocr")


def _detectar_tesseract() -> bool:  # pragma: no cover - depende del entorno
    if not (img._TESSERACT_IMPORTADO and img._OPENCV_DISPONIBLE):
        return False
    try:
        cmd = get_settings().tesseract_cmd
        if cmd:
            img.pytesseract.pytesseract.tesseract_cmd = cmd
        img.pytesseract.get_tesseract_version()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Tesseract no disponible: %s", exc)
        return False


_TESSERACT_DISPONIBLE = _detectar_tesseract()

# Cada pasada de Tesseract se corta a los N segundos y el análisis completo de
# una foto tiene un presupuesto total: el OCR nunca debe colgar la subida.
_TIMEOUT_PASADA_SEG = 20
_PRESUPUESTO_SEG = 45

_ETIQUETAS = {
    "numero_documento": "número de documento",
    "nombres": "nombres",
    "apellidos": "apellidos",
    "fecha_nacimiento": "fecha de nacimiento",
    "sexo": "sexo",
    "lugar_nacimiento": "lugar de nacimiento",
    "fecha_expedicion": "fecha de expedición",
    "ciudad_expedicion": "ciudad de expedición",
    "fecha_expiracion": "fecha de expiración",
}
_NOMBRE_LADO = {"cedula_frontal": "anverso", "cedula_reverso": "reverso"}


# --------------------------------------------------------------------------
# Estructuras de resultado
# --------------------------------------------------------------------------


@dataclass
class CampoOCR:
    """Un campo extraído, con la confianza (0-100) y de dónde salió."""

    valor: str = ""
    confianza: float = 0.0
    fuente: str = ""  # mrz | anverso | reverso | codigo_reverso


@dataclass
class LecturaCara:
    """Lo que se leyó de UNA foto (anverso o reverso)."""

    disponible: bool = False
    tipo_cedula: str | None = None  # blanca | amarilla
    cara: str | None = None  # frontal | reverso
    campos: dict[str, CampoOCR] = field(default_factory=dict)
    mrz_valido: bool = False
    recorte: str = ""  # geometria | texto | completa
    pasadas: int = 0
    tiempo_ms: int = 0
    texto_crudo: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, datos: dict) -> "LecturaCara":
        campos = {
            k: CampoOCR(**v) for k, v in (datos.get("campos") or {}).items()
            if isinstance(v, dict)
        }
        conocidos = {k: v for k, v in datos.items() if k in cls.__dataclass_fields__ and k != "campos"}
        return cls(campos=campos, **conocidos)


@dataclass
class ResultadoOCR:
    """Resultado fusionado (anverso + reverso) + advertencias de la comparación."""

    disponible: bool = False
    texto_crudo: str = ""
    tipo_cedula: str = ""
    numero_documento: CampoOCR = field(default_factory=CampoOCR)
    nombres: CampoOCR = field(default_factory=CampoOCR)
    apellidos: CampoOCR = field(default_factory=CampoOCR)
    fecha_nacimiento: CampoOCR = field(default_factory=CampoOCR)
    fecha_expedicion: CampoOCR = field(default_factory=CampoOCR)
    fecha_expiracion: CampoOCR = field(default_factory=CampoOCR)
    sexo: CampoOCR = field(default_factory=CampoOCR)
    lugar_nacimiento: CampoOCR = field(default_factory=CampoOCR)
    ciudad_expedicion: CampoOCR = field(default_factory=CampoOCR)
    # Diferencias que el asesor debe revisar (afectan ``coincide``).
    advertencias: list[str] = field(default_factory=list)
    # Notas de calidad de la captura (no afectan ``coincide``).
    observaciones: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serializa a JSON (el frontend consume snake_case del backend)."""
        datos = asdict(self)
        datos["coincide"] = not self.advertencias
        return datos


# --------------------------------------------------------------------------
# Análisis de una foto
# --------------------------------------------------------------------------


def _a_campos(lectura: LecturaParseada | dict) -> dict[str, CampoOCR]:
    campos = lectura.campos if isinstance(lectura, LecturaParseada) else lectura
    return {k: CampoOCR(v.valor, round(v.conf, 1), v.fuente) for k, v in campos.items() if v.valor}


def _elegir_recorte(rgb, idioma: str, inicio: float):
    """Devuelve (imagen, metodo, lineas_primera_pasada, tipo, cara)."""
    gris = img.a_gris(rgb)

    def primera(imagen):
        lineas = img.ocr_lineas(img.escalar(imagen), idioma, 4, _TIMEOUT_PASADA_SEG)
        tipo, cara, _ = clasificar(lineas)
        return lineas, tipo, cara

    # 1) Contorno de la tarjeta (proporción ID-1). Se prueba también girada
    #    180° por si la foto quedó al revés.
    geo = img.localizar_por_geometria(rgb)
    if geo is not None:
        geo = img.a_horizontal(geo)
        for grados in (0, 180):
            candidata = img.rotar(geo, grados)
            lineas, tipo, cara = primera(candidata)
            if tipo:
                return candidata, "geometria", lineas, tipo, cara
            if time.monotonic() - inicio > _PRESUPUESTO_SEG / 2:
                break

    # 2) Recorte guiado por los rótulos impresos (tarjeta clara sobre fondo claro).
    #    Si la foto está girada no aparecen rótulos: se prueba la rotación que
    #    sugiere el OSD y luego las demás (el OSD falla a menudo con cédulas).
    recorte, _ = img.localizar_por_texto(gris, idioma, _TIMEOUT_PASADA_SEG)
    if recorte is None:
        sugerida = img.rotacion_osd(gris, _TIMEOUT_PASADA_SEG)
        orden = [g for g in dict.fromkeys((sugerida, 180, 90, 270)) if g]
        for grados in orden:
            if time.monotonic() - inicio > _PRESUPUESTO_SEG / 2:
                break
            girada = img.rotar(gris, grados)
            recorte, _ = img.localizar_por_texto(girada, idioma, _TIMEOUT_PASADA_SEG)
            if recorte is not None:
                gris = girada
                break
    if recorte is not None:
        lineas, tipo, cara = primera(recorte)
        return recorte, "texto", lineas, tipo, cara

    # 3) Último recurso: la foto completa.
    lineas, tipo, cara = primera(gris)
    return gris, "completa", lineas, tipo, cara


def _banda_mrz(imagen, lineas) -> "img.np.ndarray":
    ys = [ln.y for ln in lineas if "<" in ln.texto]
    alto = imagen.shape[0]
    if ys:
        y0, y1 = max(0.0, min(ys) - 0.15), min(1.0, max(ys) + 0.15)
    else:
        y0, y1 = 0.45, 1.0
    return imagen[int(y0 * alto) : int(y1 * alto), :]


def analizar_cara(ruta: Path, lado_declarado: str | None = None) -> LecturaCara:
    """Analiza una foto de la cédula. Nunca lanza: si falla, ``disponible=False``.

    ``lado_declarado`` (frontal/reverso) solo se usa si el contenido no permite
    reconocer la cara.
    """
    inicio = time.monotonic()
    if not _TESSERACT_DISPONIBLE:
        return LecturaCara(error="Tesseract no está disponible en este entorno")
    idioma = get_settings().tesseract_lang or "spa"
    try:
        rgb = img.cargar_imagen(ruta)
        imagen, metodo, lineas, tipo, cara = _elegir_recorte(rgb, idioma, inicio)
        if cara is None and lado_declarado in (CARA_FRONTAL, CARA_REVERSO):
            cara = lado_declarado
        votos = Votacion()
        primera = parsear_lineas(lineas, tipo, cara)
        votos.agregar(primera.campos)
        pasadas = 1
        mejor_mrz = primera if primera.mrz_valido else None
        base = img.escalar(imagen)

        if tipo == TIPO_BLANCA and cara == CARA_REVERSO:
            # MRZ: lista blanca de caracteres; se para cuando validan los dígitos de control.
            intentos = (
                (img.variante(base, "gris"), 6),
                (img.variante(img.escalar(_banda_mrz(imagen, lineas)), "gris"), 6),
                (img.variante(base, "fondo"), 6),
            )
            for imagen_mrz, psm in intentos:
                if mejor_mrz or time.monotonic() - inicio > _PRESUPUESTO_SEG:
                    break
                lineas_mrz = img.ocr_lineas(
                    imagen_mrz, idioma, psm, _TIMEOUT_PASADA_SEG, img.LISTA_BLANCA_MRZ
                )
                pasadas += 1
                lectura = parsear_lineas(lineas_mrz, tipo, cara)
                votos.agregar(lectura.campos)
                if lectura.mrz_valido:
                    mejor_mrz = lectura
        elif tipo is not None or metodo != "completa":
            esperados = CAMPOS_POR_CARA.get((tipo, cara), ())
            for modo, psm in (("fondo", 6), ("gris", 6), ("fondo", 4)):
                if esperados and votos.estable(esperados):
                    break
                if time.monotonic() - inicio > _PRESUPUESTO_SEG:
                    break
                lineas_extra = img.ocr_lineas(
                    img.variante(base, modo), idioma, psm, _TIMEOUT_PASADA_SEG
                )
                pasadas += 1
                if tipo is None:
                    tipo_extra, cara_extra, _ = clasificar(lineas_extra)
                    if tipo_extra:
                        tipo, cara = tipo_extra, cara_extra
                        esperados = CAMPOS_POR_CARA.get((tipo, cara), ())
                votos.agregar(parsear_lineas(lineas_extra, tipo, cara).campos)

        campos = _a_campos(votos.resultado())
        if mejor_mrz:  # validado por dígitos de control: no se vota
            campos.update(_a_campos(mejor_mrz))
        return LecturaCara(
            disponible=True,
            tipo_cedula=tipo,
            cara=cara,
            campos=campos,
            mrz_valido=bool(mejor_mrz),
            recorte=metodo,
            pasadas=pasadas,
            tiempo_ms=int((time.monotonic() - inicio) * 1000),
            texto_crudo=img.texto_de(lineas)[:4000],
        )
    except Exception as exc:  # noqa: BLE001 - el OCR es best-effort
        logger.warning("OCR no disponible para %s: %s", ruta, exc)
        return LecturaCara(
            error=f"No se pudo procesar la imagen: {exc.__class__.__name__}",
            tiempo_ms=int((time.monotonic() - inicio) * 1000),
        )


# --------------------------------------------------------------------------
# Fusión anverso + reverso
# --------------------------------------------------------------------------


def _rango(campo: str, c: CampoOCR) -> float:
    """Prioridad de una fuente para un campo (mayor = manda)."""
    if c.fuente == "mrz":
        if campo in ("numero_documento", "fecha_nacimiento", "fecha_expiracion", "sexo"):
            return 3.0 if c.confianza >= 95 else 1.5
        # Nombres: el MRZ no trae dígito de control para ellos; compite por
        # confianza con el anverso en igualdad de condiciones.
        return 2.0
    if c.fuente == "codigo_reverso":
        return 1.0
    return 2.0


def _clave(campo: str, valor: str) -> str:
    if campo in ("nombres", "apellidos", "lugar_nacimiento", "ciudad_expedicion"):
        return re.sub(r"[^A-Z]", "", plano_ascii(valor))
    return re.sub(r"\D", "", valor).lstrip("0") if campo == "numero_documento" else valor


def fusionar_lecturas(lecturas: dict[str, dict]) -> ResultadoOCR:
    """Combina las lecturas por foto (``{"cedula_frontal": {...}, ...}``)."""
    objetos = {k: LecturaCara.from_dict(v) for k, v in lecturas.items() if isinstance(v, dict)}
    validas = {k: v for k, v in objetos.items() if v.disponible}
    resultado = ResultadoOCR(disponible=bool(validas))
    for lado, lectura in objetos.items():
        nombre = _NOMBRE_LADO.get(lado, lado)
        if not lectura.disponible:
            resultado.observaciones.append(f"No se pudo procesar la foto del {nombre}.")
        elif lectura.tipo_cedula is None:
            resultado.observaciones.append(
                f"No se reconoció la cédula en el {nombre}: repite la foto con buena luz."
            )
        elif lado in _NOMBRE_LADO and lectura.cara and _NOMBRE_LADO[lado] != (
            "anverso" if lectura.cara == CARA_FRONTAL else "reverso"
        ):
            otro = "anverso" if lectura.cara == CARA_FRONTAL else "reverso"
            resultado.observaciones.append(
                f"La foto del {nombre} parece ser el {otro}."
            )
    if not validas:
        return resultado

    tipos = {v.tipo_cedula for v in validas.values() if v.tipo_cedula}
    if len(tipos) > 1:
        resultado.advertencias.append(
            "El anverso y el reverso son de cédulas distintas."
        )
    frontal = next((v for v in validas.values() if v.cara == CARA_FRONTAL and v.tipo_cedula), None)
    resultado.tipo_cedula = (frontal.tipo_cedula if frontal else next(iter(tipos), None)) or ""

    # Con caras de cédulas distintas no se mezclan campos: manda la del anverso.
    fuentes = validas
    if len(tipos) > 1 and resultado.tipo_cedula:
        fuentes = {k: v for k, v in validas.items() if v.tipo_cedula == resultado.tipo_cedula}
    for campo in CAMPOS:
        candidatos = [v.campos[campo] for v in fuentes.values() if campo in v.campos and v.campos[campo].valor]
        if not candidatos:
            continue
        elegido = max(candidatos, key=lambda c: (_rango(campo, c), c.confianza))
        if campo in ("nombres", "apellidos"):
            de_anverso = next((c for c in candidatos if c.fuente == "anverso"), None)
            de_mrz = next((c for c in candidatos if c.fuente == "mrz"), None)
            if de_anverso and de_mrz:
                if _clave(campo, de_anverso.valor) == _clave(campo, de_mrz.valor):
                    # Coinciden: se conserva el anverso (trae Ñ y tildes).
                    elegido = CampoOCR(
                        de_anverso.valor, max(de_anverso.confianza, de_mrz.confianza), "anverso"
                    )
                else:
                    resultado.observaciones.append(
                        f"Los {campo} no coinciden: anverso ({de_anverso.valor}) vs reverso ({de_mrz.valor})."
                    )
        setattr(resultado, campo, CampoOCR(elegido.valor, elegido.confianza, elegido.fuente))

    # Cruce anverso vs reverso del número: detecta fotos de dos cédulas distintas.
    numeros = {
        c.fuente: _clave("numero_documento", c.valor)
        for v in validas.values()
        for k, c in v.campos.items()
        if k == "numero_documento" and c.valor and c.confianza >= 70
    }
    anverso = numeros.get("anverso")
    reverso = numeros.get("mrz") or numeros.get("codigo_reverso")
    if anverso and reverso and anverso != reverso:
        resultado.advertencias.append(
            f"Número distinto: anverso ({anverso}) vs reverso ({reverso})."
        )

    expira = resultado.fecha_expiracion.valor
    if expira and expira < date.today().isoformat():
        resultado.advertencias.append(f"La cédula está vencida (fecha de expiración {expira}).")

    if frontal or len(validas) > 1:
        tipo = resultado.tipo_cedula
        requeridos = set()
        for (t, _), campos in CAMPOS_POR_CARA.items():
            if t == tipo:
                requeridos.update(campos)
        faltantes = [
            _ETIQUETAS[c] for c in CAMPOS
            if c in requeridos and not getattr(resultado, c).valor
        ]
        if faltantes and len(validas) >= 2:
            resultado.observaciones.append(
                "No se leyó: " + ", ".join(faltantes) + ". Digítalos del físico."
            )

    resultado.texto_crudo = "\n\n".join(
        f"[{_NOMBRE_LADO.get(k, k)}]\n{v.texto_crudo}" for k, v in validas.items() if v.texto_crudo
    )
    return resultado


# --------------------------------------------------------------------------
# Comparación contra los datos esperados (capturados por el asesor)
# --------------------------------------------------------------------------

# Mínimo de coincidencia de nombre para no marcar falsos positivos cuando el
# OCR lee parcialmente (p. ej. solo el primer nombre).
_UMBRAL_NOMBRE = 0.6


def _normalizar_nombre(texto: str) -> set[str]:
    return {p for p in re.split(r"\s+", plano_ascii(texto).strip()) if len(p) > 1}


def _coincide_nombre(esperado: str, leido: str) -> bool:
    """True si el nombre leído cubre al menos el 60 % de lo esperado.

    Tolera palabras pegadas por el OCR (``CARLOSMARIO``) y la Ñ del MRZ (N).
    """
    conjunto_esperado = _normalizar_nombre(esperado)
    if not conjunto_esperado:
        return False
    leido_pegado = plano_ascii(leido).replace(" ", "")
    conjunto_leido = _normalizar_nombre(leido)
    cubiertas = sum(
        1 for p in conjunto_esperado if p in conjunto_leido or p in leido_pegado
    )
    return cubiertas / len(conjunto_esperado) >= _UMBRAL_NOMBRE


def comparar_con_esperados(resultado: ResultadoOCR, esperados: dict[str, str]) -> ResultadoOCR:
    """Agrega advertencias cuando un campo leído no concuerda con lo esperado.

    No bloquea. Un campo que el OCR no logró leer no genera advertencia (el
    asesor lo confirma a mano).
    """
    if not esperados:
        return resultado
    advertencias = list(resultado.advertencias)

    cedula_esperada = re.sub(r"\D", "", esperados.get("numero_documento") or "")
    cedula_leida = re.sub(r"\D", "", resultado.numero_documento.valor)
    if cedula_esperada and cedula_leida and cedula_leida != cedula_esperada:
        advertencias.append(
            f"N.º documento distinto: leído ({cedula_leida}) vs capturado ({cedula_esperada})."
        )

    for clave in ("nombres", "apellidos"):
        esperado = (esperados.get(clave) or "").strip()
        leido = getattr(resultado, clave).valor
        if esperado and leido and not _coincide_nombre(esperado, leido):
            advertencias.append(
                f"{clave.capitalize()} distintos: leídos ({leido}) vs capturados ({esperado})."
            )

    fecha_esperada = (esperados.get("fecha_nacimiento") or "").strip()[:10]
    if fecha_esperada and resultado.fecha_nacimiento.valor and \
            resultado.fecha_nacimiento.valor != fecha_esperada:
        advertencias.append(
            f"Fecha de nacimiento distinta: leída ({resultado.fecha_nacimiento.valor}) "
            f"vs capturada ({fecha_esperada})."
        )

    resultado.advertencias = list(dict.fromkeys(advertencias))
    return resultado


# --------------------------------------------------------------------------
# API pública
# --------------------------------------------------------------------------


def procesar_foto_cedula(
    resultado_previo: dict | None,
    tipo_evidencia: str,
    ruta: Path,
    esperados: dict[str, str] | None = None,
) -> dict:
    """Analiza una foto nueva y recalcula el resultado fusionado de la sesión.

    ``resultado_previo`` es lo guardado en ``sesion_captura.resultado_ocr``;
    trae en ``lecturas`` lo leído de cada foto, así anverso y reverso se
    fusionan sin importar el orden de subida y una foto repetida reemplaza a
    la anterior. Devuelve un dict NUEVO (para que SQLAlchemy detecte el cambio
    en la columna JSON).
    """
    lecturas = dict((resultado_previo or {}).get("lecturas") or {})
    lado = CARA_FRONTAL if tipo_evidencia == "cedula_frontal" else CARA_REVERSO
    lecturas[tipo_evidencia] = analizar_cara(ruta, lado).to_dict()
    resultado = comparar_con_esperados(fusionar_lecturas(lecturas), esperados or {})
    salida = resultado.to_dict()
    salida["lecturas"] = lecturas
    return salida


def leer_cedula(ruta: Path, esperados: dict[str, str] | None = None) -> ResultadoOCR:
    """OCR de una sola foto (cualquier cara) comparado contra lo esperado.

    Nunca lanza: en el peor caso devuelve ``disponible=False``.
    """
    lectura = analizar_cara(ruta)
    resultado = fusionar_lecturas({"cedula_frontal": lectura.to_dict()})
    if not lectura.disponible:
        resultado.advertencias = []
        resultado.observaciones = ["No se pudo procesar el OCR de la cédula."]
    return comparar_con_esperados(resultado, esperados or {})


def leer_mrz_reverso(ruta: Path) -> dict:
    """Compatibilidad: campos del MRZ del reverso como dict serializable."""
    lectura = analizar_cara(ruta, CARA_REVERSO)
    if not lectura.disponible or not lectura.mrz_valido and not any(
        c.fuente == "mrz" for c in lectura.campos.values()
    ):
        return {}
    salida: dict = {"disponible": True}
    for clave, campo in lectura.campos.items():
        if campo.fuente == "mrz":
            salida[clave] = {"valor": campo.valor, "confianza": campo.confianza}
    return salida
