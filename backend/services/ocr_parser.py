"""Parser de la cédula de ciudadanía colombiana a partir de la salida de Tesseract.

No depende del binario de Tesseract: recibe líneas con palabras, confianza y
posición (normalizada 0-1 respecto al recorte de la tarjeta) y devuelve los
campos. Así se prueba de forma determinista.

Diseños soportados
------------------
**Cédula amarilla (hologramas, 2000-2020)**

- Anverso: el rótulo va DEBAJO del valor (``GARCIA SALAZAR`` / ``APELLIDOS``),
  salvo ``NUMERO 1.006.308.061`` que va en la misma línea.
- Reverso: ``FECHA DE NACIMIENTO 09-NOV-2002`` en la misma línea; lugar de
  nacimiento, estatura/RH/sexo y fecha-lugar de expedición con el valor ENCIMA
  del rótulo. Al pie, una línea ``P-...-M-<cédula>-<fecha>`` con sexo y número.

**Cédula blanca (digital, 2020+)**

- Anverso: rótulo pequeño ENCIMA del valor (``Apellidos`` / ``RIOS RIASCOS``),
  ``NUIP 1.006.461.914`` en la misma línea.
- Reverso: MRZ ICAO 9303 TD1 (3 líneas de 30 caracteres) con dígitos de
  control: es la fuente más fiable de número, nombres, nacimiento, sexo y
  expiración.

Tesseract confunde letras y dígitos, pega palabras y lee mal los rótulos
(``Apalidos``, ``Fethade nacimiento``): los rótulos se reconocen por
similitud difusa y los valores por posición relativa al rótulo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher

# --------------------------------------------------------------------------
# Estructuras
# --------------------------------------------------------------------------

TIPO_BLANCA = "blanca"
TIPO_AMARILLA = "amarilla"
CARA_FRONTAL = "frontal"
CARA_REVERSO = "reverso"

CAMPOS = (
    "numero_documento",
    "nombres",
    "apellidos",
    "fecha_nacimiento",
    "sexo",
    "lugar_nacimiento",
    "fecha_expedicion",
    "ciudad_expedicion",
    "fecha_expiracion",
)

# Campos que cada cara puede aportar (para decidir cuándo dejar de hacer pasadas).
CAMPOS_POR_CARA: dict[tuple[str, str], tuple[str, ...]] = {
    (TIPO_BLANCA, CARA_FRONTAL): (
        "numero_documento", "nombres", "apellidos", "fecha_nacimiento", "sexo",
        "lugar_nacimiento", "fecha_expedicion", "ciudad_expedicion",
        "fecha_expiracion",
    ),
    (TIPO_BLANCA, CARA_REVERSO): (
        "numero_documento", "nombres", "apellidos", "fecha_nacimiento", "sexo",
        "fecha_expiracion",
    ),
    (TIPO_AMARILLA, CARA_FRONTAL): ("numero_documento", "nombres", "apellidos"),
    (TIPO_AMARILLA, CARA_REVERSO): (
        "fecha_nacimiento", "lugar_nacimiento", "fecha_expedicion",
        "ciudad_expedicion", "sexo",
    ),
}


@dataclass
class Palabra:
    texto: str
    conf: float
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Linea:
    palabras: list[Palabra]

    @property
    def texto(self) -> str:
        return " ".join(p.texto for p in self.palabras)

    @property
    def y(self) -> float:
        if not self.palabras:
            return 0.0
        return sum((p.y0 + p.y1) / 2 for p in self.palabras) / len(self.palabras)


@dataclass
class Rotulo:
    clave: str  # APELLIDOS, NOMBRES, NUIP, NUMERO, SEXO, FECHA_NAC, LUGAR_NAC, EXPEDICION, EXPIRACION
    linea: int
    x0: float
    x1: float
    fin: int  # índice de la última palabra del rótulo en la línea


@dataclass
class Valor:
    valor: str
    conf: float
    fuente: str = ""


@dataclass
class LecturaParseada:
    tipo: str | None
    cara: str | None
    campos: dict[str, Valor] = field(default_factory=dict)
    mrz_valido: bool = False


# --------------------------------------------------------------------------
# Utilidades de texto
# --------------------------------------------------------------------------


def plano(texto: str) -> str:
    """Sin acentos y en mayúsculas (la Ñ se conserva)."""
    texto = texto.replace("ñ", "\0").replace("Ñ", "\0")
    sin = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return sin.upper().replace("\0", "Ñ")


def plano_ascii(texto: str) -> str:
    """Como ``plano`` pero Ñ→N (para comparar contra el MRZ)."""
    return plano(texto).replace("Ñ", "N")


def lineas_desde_texto(texto: str) -> list[Linea]:
    """Construye líneas sintéticas a partir de texto plano (para pruebas).

    La posición horizontal sale de la columna del carácter, así que los
    espacios iniciales sirven para simular la maquetación.
    """
    filas = [f for f in texto.splitlines() if f.strip()]
    if not filas:
        return []
    ancho = max(len(f) for f in filas) or 1
    lineas: list[Linea] = []
    for i, fila in enumerate(filas):
        palabras = []
        for m in re.finditer(r"\S+", fila):
            palabras.append(
                Palabra(
                    texto=m.group(),
                    conf=95.0,
                    x0=m.start() / ancho,
                    x1=m.end() / ancho,
                    y0=i / len(filas),
                    y1=(i + 0.8) / len(filas),
                )
            )
        lineas.append(Linea(palabras))
    return lineas


# --------------------------------------------------------------------------
# Reconocimiento difuso de rótulos
# --------------------------------------------------------------------------

_VOCABULARIO = (
    "REPUBLICA", "COLOMBIA", "CEDULA", "CIUDADANIA", "IDENTIFICACION",
    "PERSONAL", "NUIP", "NUMERO", "APELLIDOS", "NOMBRES", "NACIONALIDAD",
    "NACIONAL", "ESTATURA", "SEXO", "FECHA", "NACIMIENTO", "LUGAR",
    "EXPEDICION", "EXPIRACION", "FIRMA", "INDICE", "DERECHO", "REGISTRADOR",
)
# Palabras de rótulo que nunca son parte de un valor.
_RUIDO = set(_VOCABULARIO) | {
    "APELLIDO", "NOMBRE", "PRIMER", "SEGUNDO", "DE", "Y", "GS", "RH", "COL",
}


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _ratio_parcial(token: str, clave: str) -> float:
    """Mejor similitud de ``clave`` contra subcadenas de ``token``."""
    if len(token) <= len(clave) + 2:
        return _ratio(token, clave)
    mejor = 0.0
    n = len(clave)
    for largo in (n - 1, n, n + 1):
        for i in range(0, len(token) - largo + 1):
            mejor = max(mejor, _ratio(token[i : i + largo], clave))
    return mejor


def claves_de_token(texto: str) -> list[str]:
    """Palabras de rótulo presentes en un token (puede venir pegado)."""
    token = re.sub(r"[^A-Z]", "", plano_ascii(texto))
    if len(token) < 4:
        return []
    # Token largo (rótulos pegados: FECHADENACIMIENTO): todas las que aparezcan.
    if len(token) > 12:
        return [c for c in _VOCABULARIO if len(c) >= 5 and _ratio_parcial(token, c) >= 0.86]
    puntajes = sorted(
        ((_ratio(token, c), c) for c in _VOCABULARIO), reverse=True
    )
    mejor_ratio, mejor = puntajes[0]
    umbral = 0.75 if len(mejor) <= 5 else 0.72
    if mejor_ratio < umbral:
        # FECHADE / FETHADE: rótulo + conector pegado.
        if len(token) >= 6:
            for c in ("FECHA", "LUGAR", "NACIMIENTO", "EXPEDICION"):
                if _ratio_parcial(token, c) >= 0.8:
                    return [c]
        return []
    return [mejor]


def _rotulos_de_linea(linea: Linea, indice: int) -> list[Rotulo]:
    claves_por_palabra = [claves_de_token(p.texto) for p in linea.palabras]
    planas = [c for claves in claves_por_palabra for c in claves]
    rotulos: list[Rotulo] = []

    def span(*buscadas: str) -> tuple[float, float, int] | None:
        idx = [i for i, cl in enumerate(claves_por_palabra) if any(b in cl for b in buscadas)]
        if not idx:
            return None
        return linea.palabras[idx[0]].x0, linea.palabras[idx[-1]].x1, idx[-1]

    simples = {
        "APELLIDOS": "APELLIDOS",
        "NOMBRES": "NOMBRES",
        "NUIP": "NUIP",
        "NUMERO": "NUMERO",
        "SEXO": "SEXO",
        "ESTATURA": "ESTATURA",
    }
    for clave_vocab, clave in simples.items():
        if clave_vocab in planas:
            s = span(clave_vocab)
            if s:
                rotulos.append(Rotulo(clave, indice, s[0], s[1], s[2]))
    if "EXPIRACION" in planas:
        s = span("FECHA", "EXPIRACION")
        rotulos.append(Rotulo("EXPIRACION", indice, s[0], s[1], span("EXPIRACION")[2]))
    if "EXPEDICION" in planas:
        s = span("FECHA", "LUGAR", "EXPEDICION")
        if s:
            rotulos.append(Rotulo("EXPEDICION", indice, s[0], s[1], span("EXPEDICION")[2]))
    elif "NACIMIENTO" in planas:
        if "LUGAR" in planas:
            s = span("LUGAR", "NACIMIENTO")
            rotulos.append(Rotulo("LUGAR_NAC", indice, s[0], s[1], s[2]))
        else:
            s = span("FECHA", "NACIMIENTO")
            rotulos.append(Rotulo("FECHA_NAC", indice, s[0], s[1], span("NACIMIENTO")[2]))
    return rotulos


def detectar_rotulos(lineas: list[Linea]) -> list[Rotulo]:
    rotulos: list[Rotulo] = []
    for i, linea in enumerate(lineas):
        rotulos.extend(_rotulos_de_linea(linea, i))
    return rotulos


def _es_linea_rotulo(linea: Linea) -> bool:
    return any(claves_de_token(p.texto) for p in linea.palabras)


# --------------------------------------------------------------------------
# MRZ (reverso de la cédula blanca) — ICAO 9303 TD1
# --------------------------------------------------------------------------

_A_DIGITO = str.maketrans({"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1",
                           "L": "1", "T": "1", "Z": "2", "S": "5", "B": "8",
                           "G": "6", "A": "4"})
_A_LETRA = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B",
                          "6": "G", "4": "A"})


def _digito_control(datos: str) -> int:
    pesos = (7, 3, 1)
    total = 0
    for i, c in enumerate(datos):
        if c.isdigit():
            v = int(c)
        elif "A" <= c <= "Z":
            v = ord(c) - 55
        else:
            v = 0
        total += v * pesos[i % 3]
    return total % 10


def _normalizar_mrz(linea: str) -> str:
    s = plano_ascii(linea).replace(" ", "")
    s = s.replace("«", "<<").replace("‹", "<").replace("(", "<")
    return re.sub(r"[^A-Z0-9<]", "", s)


def _anio_nacimiento(yy: int) -> int:
    actual = date.today().year % 100
    return 2000 + yy if yy <= actual else 1900 + yy


def _iso_yymmdd(texto: str, nacimiento: bool) -> str | None:
    if not re.fullmatch(r"\d{6}", texto):
        return None
    yy, mm, dd = int(texto[:2]), int(texto[2:4]), int(texto[4:])
    anio = _anio_nacimiento(yy) if nacimiento else 2000 + yy
    try:
        return date(anio, mm, dd).isoformat()
    except ValueError:
        return None


def _es_linea2(s: str) -> str | None:
    """Corrige la línea 2 por posición; None si no tiene forma de línea 2.

    La nacionalidad (COL) va en las posiciones 15-17: se usa para alinear la
    línea cuando el OCR pega basura del borde al inicio (``1`` + ``0204244M…``).
    """
    if len(s) < 18:
        return None
    m = re.search(r"C[O0Q]L", s[10:26])
    if not m:
        return None
    desfase = 10 + m.start() - 15
    if desfase < 0:
        return None
    s = s[desfase:]
    nacimiento = s[0:7].translate(_A_DIGITO)
    sexo = s[7] if s[7] in "MF<" else {"H": "M", "N": "M", "P": "F", "E": "F"}.get(s[7], "<")
    expira = s[8:15].translate(_A_DIGITO)
    resto = s[18:]
    opcional = re.match(r"[^<]*", resto).group().translate(_A_DIGITO)
    resto = opcional + resto[len(opcional) :]
    corregida = (nacimiento + sexo + expira + "COL" + resto)[:30]
    if len(corregida) == 29:
        return None if not corregida.endswith("<") else corregida + "<"
    if not re.fullmatch(r"\d{7}[MF<]\d{7}COL.*", corregida):
        return None
    if len(corregida) == 30 and not corregida[29].isdigit():
        corregida = corregida[:29] + corregida[29].translate(_A_DIGITO)
    return corregida


def _corregir_linea1(s: str) -> str:
    s = s.ljust(30, "<")  # Tesseract suele omitir parte del relleno final
    m = re.search(r"C[O0Q]L", s[:6])
    if m:
        s = "IC" + "COL" + s[m.end() :]
    numero = s[5:15].translate(_A_DIGITO)
    resto = s[15:]
    opcional = re.match(r"[^<]*", resto).group().translate(_A_DIGITO)
    return (s[:5] + numero + opcional + resto[len(opcional) :]).ljust(30, "<")


def _limpiar_nombre_mrz(parte: str) -> str:
    parte = re.sub(r"[<K]+$", "", parte)  # relleno final (a veces leído como K)
    palabras = [p for p in parte.split("<") if p]
    palabras = [p.translate(_A_LETRA) for p in palabras]
    palabras = [p for p in palabras if re.fullmatch(r"[A-Z]{1,}", p)]
    return " ".join(palabras)


def parsear_mrz(texto_o_lineas: str | list[str]) -> dict:
    """Extrae los campos del MRZ TD1. Devuelve {} si no hay MRZ legible.

    Claves: numero_documento, apellidos, nombres, fecha_nacimiento, sexo,
    fecha_expiracion, y los booleanos ``control_nacimiento``,
    ``control_expiracion`` y ``control_compuesto``.
    """
    crudas = (
        texto_o_lineas.splitlines() if isinstance(texto_o_lineas, str) else texto_o_lineas
    )
    lineas = [_normalizar_mrz(ln) for ln in crudas]
    lineas = [ln for ln in lineas if len(ln) >= 18]
    idx2 = None
    linea2 = ""
    for i, ln in enumerate(lineas):
        corregida = _es_linea2(ln)
        if corregida:
            idx2, linea2 = i, corregida
            break
    if idx2 is None:
        return {}

    salida: dict = {}
    nac = _iso_yymmdd(linea2[0:6], nacimiento=True)
    ctrl_nac = _digito_control(linea2[0:6]) == int(linea2[6])
    if nac:
        salida["fecha_nacimiento"] = nac
    salida["control_nacimiento"] = bool(nac) and ctrl_nac
    if linea2[7] in "MF":
        salida["sexo"] = linea2[7]
    exp = _iso_yymmdd(linea2[8:14], nacimiento=False)
    if exp:
        salida["fecha_expiracion"] = exp
    salida["control_expiracion"] = bool(exp) and _digito_control(linea2[8:14]) == int(linea2[14])

    # NUIP en el dato opcional de la línea 2 (posiciones 18-28).
    nuip = re.match(r"\d{6,11}", linea2[18:])
    if nuip:
        salida["numero_documento"] = nuip.group()[:10]

    # Dígito compuesto: línea 1 [5:30] + línea 2 [0:7] + [8:15] + [18:29].
    salida["control_compuesto"] = False
    if idx2 > 0 and len(linea2) >= 30:
        linea1 = _corregir_linea1(lineas[idx2 - 1])
        if len(linea1) >= 30:
            datos = linea1[5:30] + linea2[0:7] + linea2[8:15] + linea2[18:29]
            salida["control_compuesto"] = (
                linea2[29].isdigit() and _digito_control(datos) == int(linea2[29])
            )

    # Línea 3: APELLIDOS<<NOMBRES
    candidatas = lineas[idx2 + 1 :] + lineas[:idx2]
    for ln in candidatas:
        if "<" not in ln or sum(c.isdigit() for c in ln) > 3:
            continue
        cuerpo = ln.lstrip("<")
        if "<<" not in cuerpo:
            continue
        apellidos_crudo, _, nombres_crudo = cuerpo.partition("<<")
        # Los nombres terminan en el relleno ``<<``: lo que siga es ruido.
        nombres_crudo = nombres_crudo.split("<<")[0]
        apellidos = _limpiar_nombre_mrz(apellidos_crudo)
        nombres = _limpiar_nombre_mrz(nombres_crudo)
        if apellidos:
            salida["apellidos"] = apellidos
        if nombres:
            salida["nombres"] = nombres
        break
    return salida


def _lineas_mrz(lineas: list[Linea]) -> list[str]:
    return [ln.texto for ln in lineas if "<" in ln.texto or len(_normalizar_mrz(ln.texto)) >= 26]


# --------------------------------------------------------------------------
# Fechas, números y nombres
# --------------------------------------------------------------------------

_MESES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
    "AGO": 8, "SEP": 9, "SET": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}
_RE_FECHA = re.compile(
    r"(?<!\d)([0-9O]{1,2})\s*[-/.,]?\s*([A-Z0]{3,5})\.?\s*[-/.,]?\s*([0-9O]{4})(?!\d)"
)


def _mes(token: str) -> int | None:
    token = token.replace("0", "O")[:3]
    if token in _MESES:
        return _MESES[token]
    mejor = max(_MESES, key=lambda m: _ratio(token, m))
    return _MESES[mejor] if _ratio(token, mejor) >= 0.67 else None


def buscar_fecha(texto: str, tipo: str) -> tuple[str, int, int] | None:
    """Primera fecha válida ``dd MMM yyyy`` del texto: (iso, inicio, fin).

    ``tipo``: nacimiento | expedicion | expiracion (define el rango de años
    válido, así un 1991 leído como 1091 se descarta en vez de colarse).
    """
    normal = plano_ascii(texto)
    hoy = date.today()
    for m in _RE_FECHA.finditer(normal):
        mes = _mes(m.group(2))
        if not mes:
            continue
        try:
            dia = int(m.group(1).replace("O", "0"))
            anio = int(m.group(3).replace("O", "0"))
            valor = date(anio, mes, dia)
        except ValueError:
            continue
        if tipo == "nacimiento" and not (1900 <= anio and valor <= hoy):
            continue
        if tipo == "expedicion" and not (1950 <= anio and valor <= hoy):
            continue
        if tipo == "expiracion" and not (2000 <= anio <= 2100):
            continue
        return valor.isoformat(), m.start(), m.end()
    return None


def _digitos_ocr(texto: str) -> str:
    """Corrige confusiones típicas en un bloque numérico (O→0, l→1...)."""
    return texto.translate(str.maketrans({"O": "0", "o": "0", "Q": "0", "D": "0",
                                          "I": "1", "l": "1", "|": "1", "S": "5",
                                          "B": "8"}))


_RE_CEDULA_PUNTOS = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\s?\d{3}){2,3}(?![\d])")


def _numero_en_palabras(palabras: list[Palabra]) -> tuple[str, list[Palabra]] | None:
    """Une los grupos de dígitos contiguos (``1,032 448900``) en un número.

    Trabaja por palabra: un token suelto sin dígitos reales (``|`` del borde
    del holograma) corta el número en vez de convertirse en un ``1``.
    """
    usadas: list[Palabra] = []
    digitos = ""
    for p in palabras:
        reales = sum(c.isdigit() for c in p.texto)
        corregido = _digitos_ocr(p.texto.strip(".,:;"))
        if reales >= 1 and re.fullmatch(r"[\d.,]+", corregido) and reales >= len(corregido) / 2:
            digitos += re.sub(r"\D", "", corregido)
            usadas.append(p)
        elif usadas:
            break
    if 6 <= len(digitos) <= 10:
        return digitos, usadas
    return None


def _conf(palabras: list[Palabra]) -> float:
    if not palabras:
        return 0.0
    return round(sum(p.conf for p in palabras) / len(palabras), 1)


def _token_nombre(texto: str) -> str:
    limpio = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü]", "", texto)
    if len(limpio) < 2:
        return ""
    minus = sum(c.islower() for c in limpio)
    if minus > len(limpio) / 2:  # los valores de la cédula van en mayúscula
        return ""
    limpio = plano(limpio)
    if limpio in _RUIDO or claves_de_token(limpio):
        return ""
    return limpio


def _token_lugar(texto: str) -> str:
    limpio = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü().]", "", texto).strip(".")
    letras = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü]", "", limpio)
    if len(letras) < 2 or sum(c.islower() for c in letras) > len(letras) / 2:
        return ""
    limpio = plano(limpio)
    if letras.upper() in _RUIDO or claves_de_token(letras):
        return ""
    return limpio


def _palabras_en_rango(
    linea: Linea, x_min: float, x_max: float | None = None, desde: int = 0,
    tolerancia: float = 0.05, hueco_max: float = 0.08,
) -> list[Palabra]:
    """Palabras contiguas que arrancan cerca de ``x_min`` (corta en huecos grandes)."""
    candidatas = [
        p for i, p in enumerate(linea.palabras)
        if i >= desde and p.x1 > x_min - tolerancia
        and (x_max is None or p.x0 <= x_max)
    ]
    candidatas.sort(key=lambda p: p.x0)
    salida: list[Palabra] = []
    for p in candidatas:
        if salida and p.x0 - salida[-1].x1 > hueco_max:
            break
        salida.append(p)
    return salida


def _valor_nombre(palabras: list[Palabra], conf_min: float = 30) -> Valor | None:
    elegidas = [(p, _token_nombre(p.texto)) for p in palabras if p.conf >= conf_min]
    elegidas = [(p, t) for p, t in elegidas if t]
    if not elegidas:
        return None
    return Valor(" ".join(t for _, t in elegidas), _conf([p for p, _ in elegidas]))


def _valor_lugar(palabras: list[Palabra], conf_min: float = 30) -> Valor | None:
    elegidas = [(p, _token_lugar(p.texto)) for p in palabras if p.conf >= conf_min]
    elegidas = [(p, t) for p, t in elegidas if t][:5]
    if not elegidas:
        return None
    texto = " ".join(t for _, t in elegidas)
    if texto.count("(") > texto.count(")"):
        texto += ")"
    return Valor(texto, _conf([p for p, _ in elegidas]))


def _lineas_vecinas(lineas: list[Linea], i: int, direccion: int, maximo: int = 2):
    """Líneas debajo (+1) o encima (-1) del rótulo, hasta topar otro rótulo."""
    j = i + direccion
    pasos = 0
    while 0 <= j < len(lineas) and pasos < maximo:
        yield j, lineas[j]
        j += direccion
        pasos += 1


def _fecha_y_ciudad(palabras: list[Palabra], tipo: str) -> tuple[Valor | None, Valor | None]:
    if not palabras:
        return None, None
    texto = " ".join(p.texto for p in palabras)
    encontrada = buscar_fecha(texto, tipo)
    if not encontrada:
        return None, None
    iso, _, fin = encontrada
    fecha = Valor(iso, _conf(palabras))
    # Ciudad: palabras cuyo inicio queda después de la fecha.
    acumulado = 0
    tras: list[Palabra] = []
    for p in palabras:
        if acumulado >= fin:
            tras.append(p)
        acumulado += len(p.texto) + 1
    ciudad = _valor_lugar(tras)
    return fecha, ciudad


def _sexo_cerca(linea: Linea, xc: float) -> Valor | None:
    candidatos = [
        p for p in linea.palabras
        if re.sub(r"[^A-Za-z]", "", p.texto).upper() in ("M", "F")
        and len(re.sub(r"[^A-Za-z0-9]", "", p.texto)) == 1
    ]
    if not candidatos:
        return None
    p = min(candidatos, key=lambda c: abs(c.xc - xc))
    if abs(p.xc - xc) > 0.15:
        return None
    return Valor(re.sub(r"[^A-Za-z]", "", p.texto).upper(), p.conf)


# --------------------------------------------------------------------------
# Clasificación
# --------------------------------------------------------------------------

_RE_LINEA_CODIGO = re.compile(r"P-?\d{5,8}-?\d{6,9}-?([MF])-?(\d{6,10})-?\d{8}")
_RE_LINEA_CODIGO_LAXA = re.compile(r"-([MF])-(\d{6,10})-(?:19|20)\d{6}")


def _linea_codigo(lineas: list[Linea]) -> tuple[str, str, float] | None:
    for ln in lineas:
        compacto = _digitos_ocr(re.sub(r"\s+", "", ln.texto)).upper()
        m = _RE_LINEA_CODIGO.search(compacto) or _RE_LINEA_CODIGO_LAXA.search(compacto)
        if m:
            return m.group(1), m.group(2).lstrip("0"), _conf(ln.palabras)
    return None


def clasificar(lineas: list[Linea]) -> tuple[str | None, str | None, dict[str, int]]:
    """Detecta tipo (blanca/amarilla) y cara (frontal/reverso) por contenido."""
    claves: set[str] = set()
    for ln in lineas:
        for p in ln.palabras:
            claves.update(claves_de_token(p.texto))
    puntos = {
        (TIPO_BLANCA, CARA_FRONTAL): 0,
        (TIPO_BLANCA, CARA_REVERSO): 0,
        (TIPO_AMARILLA, CARA_FRONTAL): 0,
        (TIPO_AMARILLA, CARA_REVERSO): 0,
    }
    if "NUIP" in claves:
        puntos[(TIPO_BLANCA, CARA_FRONTAL)] += 3
    if "NACIONALIDAD" in claves:
        puntos[(TIPO_BLANCA, CARA_FRONTAL)] += 2
    if "EXPIRACION" in claves:
        puntos[(TIPO_BLANCA, CARA_FRONTAL)] += 2
    if parsear_mrz(_lineas_mrz(lineas)):
        puntos[(TIPO_BLANCA, CARA_REVERSO)] += 6
    if "IDENTIFICACION" in claves or "PERSONAL" in claves:
        puntos[(TIPO_AMARILLA, CARA_FRONTAL)] += 3
    if "NUMERO" in claves:
        puntos[(TIPO_AMARILLA, CARA_FRONTAL)] += 2
    if {"APELLIDOS", "NOMBRES"} & claves:
        puntos[(TIPO_AMARILLA, CARA_FRONTAL)] += 1
        puntos[(TIPO_BLANCA, CARA_FRONTAL)] += 1
    if "INDICE" in claves or "DERECHO" in claves:
        puntos[(TIPO_AMARILLA, CARA_REVERSO)] += 3
    if _linea_codigo(lineas):
        puntos[(TIPO_AMARILLA, CARA_REVERSO)] += 3
    if "ESTATURA" in claves and "NACIONALIDAD" not in claves and "NUIP" not in claves:
        puntos[(TIPO_AMARILLA, CARA_REVERSO)] += 2
    if "NACIMIENTO" in claves and not {"NUIP", "NACIONALIDAD", "EXPIRACION"} & claves:
        puntos[(TIPO_AMARILLA, CARA_REVERSO)] += 1
    mejor = max(puntos, key=lambda k: puntos[k])
    resumen = {f"{t}_{c}": v for (t, c), v in puntos.items()}
    if puntos[mejor] < 2:
        return None, None, resumen
    return mejor[0], mejor[1], resumen


# --------------------------------------------------------------------------
# Parsers por diseño
# --------------------------------------------------------------------------


def _primero(rotulos: list[Rotulo], clave: str) -> Rotulo | None:
    for r in rotulos:
        if r.clave == clave:
            return r
    return None


def _numero_por_rotulo(lineas: list[Linea], rotulos: list[Rotulo]) -> Valor | None:
    for clave in ("NUIP", "NUMERO"):
        r = _primero(rotulos, clave)
        if not r:
            continue
        palabras = _palabras_en_rango(lineas[r.linea], r.x1, desde=r.fin + 1, hueco_max=0.12)
        encontrado = _numero_en_palabras(palabras)
        if encontrado:
            return Valor(encontrado[0], _conf(encontrado[1]))
    # Respaldo: número con separadores de miles (1.006.308.061) en cualquier línea.
    for ln in lineas:
        m = _RE_CEDULA_PUNTOS.search(_digitos_ocr(ln.texto))
        if m:
            digitos = re.sub(r"\D", "", m.group())
            if 6 <= len(digitos) <= 10:
                return Valor(digitos, _conf(ln.palabras) * 0.9)
    return None


def _parsear_blanca_frontal(lineas: list[Linea]) -> dict[str, Valor]:
    rotulos = detectar_rotulos(lineas)
    lineas_rotulo = {r.linea for r in rotulos}
    campos: dict[str, Valor] = {}
    numero = _numero_por_rotulo(lineas, rotulos)
    if numero:
        campos["numero_documento"] = numero

    def debajo(clave: str, extractor) -> Valor | None:
        r = _primero(rotulos, clave)
        if not r:
            return None
        for j, ln in _lineas_vecinas(lineas, r.linea, +1):
            if j in lineas_rotulo:
                break
            palabras = _palabras_en_rango(ln, r.x0)
            valor = extractor(palabras, r) if palabras else None
            if valor:
                return valor
        return None

    nombre = lambda pal, r: _valor_nombre(pal)  # noqa: E731
    v = debajo("APELLIDOS", nombre)
    if v:
        campos["apellidos"] = v
    v = debajo("NOMBRES", nombre)
    if v:
        campos["nombres"] = v
    v = debajo("FECHA_NAC", lambda pal, r: _fecha_y_ciudad(pal, "nacimiento")[0])
    if v:
        campos["fecha_nacimiento"] = v
    v = debajo("LUGAR_NAC", lambda pal, r: _valor_lugar(pal))
    if v:
        campos["lugar_nacimiento"] = v
    r = _primero(rotulos, "EXPEDICION")
    if r:
        for _, ln in _lineas_vecinas(lineas, r.linea, +1):
            fecha, ciudad = _fecha_y_ciudad(_palabras_en_rango(ln, r.x0), "expedicion")
            if fecha:
                campos["fecha_expedicion"] = fecha
                if ciudad:
                    campos["ciudad_expedicion"] = ciudad
                break
    v = debajo("EXPIRACION", lambda pal, r: _fecha_y_ciudad(pal, "expiracion")[0])
    if v:
        campos["fecha_expiracion"] = v
    r = _primero(rotulos, "SEXO")
    if r:
        mismo = _sexo_cerca(Linea(lineas[r.linea].palabras[r.fin + 1 :]), (r.x0 + r.x1) / 2)
        if mismo:
            campos["sexo"] = mismo
        else:
            for _, ln in _lineas_vecinas(lineas, r.linea, +1, maximo=1):
                v = _sexo_cerca(ln, (r.x0 + r.x1) / 2)
                if v:
                    campos["sexo"] = v
    return campos


def _parsear_amarilla_frontal(lineas: list[Linea]) -> dict[str, Valor]:
    rotulos = detectar_rotulos(lineas)
    campos: dict[str, Valor] = {}
    numero = _numero_por_rotulo(lineas, rotulos)
    if numero:
        campos["numero_documento"] = numero
    lineas_rotulo = {r.linea for r in rotulos}
    for clave, campo in (("APELLIDOS", "apellidos"), ("NOMBRES", "nombres")):
        r = _primero(rotulos, clave)
        if not r:
            continue
        # Amarilla: el valor está ENCIMA del rótulo; se para al topar otro rótulo
        # (p. ej. la línea de NUMERO) para no tomar un valor ajeno.
        for j, ln in _lineas_vecinas(lineas, r.linea, -1):
            if j in lineas_rotulo:
                break
            v = _valor_nombre(_palabras_en_rango(ln, r.x0))
            if v:
                campos[campo] = v
                break
    return campos


def _parsear_amarilla_reverso(lineas: list[Linea]) -> dict[str, Valor]:
    rotulos = detectar_rotulos(lineas)
    lineas_rotulo = {r.linea for r in rotulos}
    campos: dict[str, Valor] = {}

    r = _primero(rotulos, "FECHA_NAC")
    if r:
        fecha, _ = _fecha_y_ciudad(lineas[r.linea].palabras[r.fin + 1 :], "nacimiento")
        if not fecha:  # valor en la línea de encima
            for _, ln in _lineas_vecinas(lineas, r.linea, -1, maximo=1):
                fecha, _ = _fecha_y_ciudad(ln.palabras, "nacimiento")
        if fecha:
            campos["fecha_nacimiento"] = fecha

    r = _primero(rotulos, "LUGAR_NAC")
    if r:
        partes: list[Palabra] = []
        for j, ln in _lineas_vecinas(lineas, r.linea, -1):
            if j in lineas_rotulo:
                break
            partes = _palabras_en_rango(ln, r.x0) + partes
        v = _valor_lugar(partes)
        if v:
            campos["lugar_nacimiento"] = v

    r = _primero(rotulos, "EXPEDICION")
    if r:
        for j, ln in _lineas_vecinas(lineas, r.linea, -1):
            if j in lineas_rotulo and j != r.linea:
                break
            fecha, ciudad = _fecha_y_ciudad(ln.palabras, "expedicion")
            if fecha:
                campos["fecha_expedicion"] = fecha
                if ciudad:
                    campos["ciudad_expedicion"] = ciudad
                break

    r = _primero(rotulos, "SEXO")
    if r:
        for _, ln in _lineas_vecinas(lineas, r.linea, -1, maximo=1):
            v = _sexo_cerca(ln, (r.x0 + r.x1) / 2)
            if v:
                campos["sexo"] = v

    codigo = _linea_codigo(lineas)
    if codigo:
        sexo, numero, conf = codigo
        campos["numero_documento"] = Valor(numero, conf, "codigo_reverso")
        if "sexo" not in campos:
            campos["sexo"] = Valor(sexo, conf, "codigo_reverso")
    return campos


def _campos_mrz(mrz: dict) -> dict[str, Valor]:
    campos: dict[str, Valor] = {}
    if not mrz:
        return campos
    compuesto = mrz.get("control_compuesto")
    if mrz.get("numero_documento"):
        campos["numero_documento"] = Valor(mrz["numero_documento"], 99.0 if compuesto else 80.0, "mrz")
    if mrz.get("fecha_nacimiento"):
        campos["fecha_nacimiento"] = Valor(
            mrz["fecha_nacimiento"], 99.0 if mrz.get("control_nacimiento") else 60.0, "mrz"
        )
    if mrz.get("fecha_expiracion"):
        campos["fecha_expiracion"] = Valor(
            mrz["fecha_expiracion"], 99.0 if mrz.get("control_expiracion") else 60.0, "mrz"
        )
    if mrz.get("sexo"):
        campos["sexo"] = Valor(mrz["sexo"], 95.0 if compuesto else 85.0, "mrz")
    for clave in ("apellidos", "nombres"):
        if mrz.get(clave):
            campos[clave] = Valor(mrz[clave], 92.0, "mrz")
    return campos


_PARSERS = {
    (TIPO_BLANCA, CARA_FRONTAL): _parsear_blanca_frontal,
    (TIPO_AMARILLA, CARA_FRONTAL): _parsear_amarilla_frontal,
    (TIPO_AMARILLA, CARA_REVERSO): _parsear_amarilla_reverso,
}


def parsear_lineas(
    lineas: list[Linea], tipo: str | None = None, cara: str | None = None
) -> LecturaParseada:
    """Parsea una pasada de OCR. Si no se indica tipo/cara, se detectan."""
    if tipo is None or cara is None:
        tipo, cara, _ = clasificar(lineas)
    if tipo == TIPO_BLANCA and cara == CARA_REVERSO:
        mrz = parsear_mrz(_lineas_mrz(lineas))
        return LecturaParseada(
            tipo, cara, _campos_mrz(mrz),
            mrz_valido=bool(mrz.get("control_nacimiento") and mrz.get("control_compuesto")),
        )
    if (tipo, cara) in _PARSERS:
        campos = _PARSERS[(tipo, cara)](lineas)
        fuente = "anverso" if cara == CARA_FRONTAL else "reverso"
        for v in campos.values():
            v.fuente = v.fuente or fuente
        return LecturaParseada(tipo, cara, campos)
    # Sin clasificar: se intentan todos y se toma lo que aparezca.
    campos: dict[str, Valor] = {}
    for (t, c), parser in _PARSERS.items():
        for k, v in parser(lineas).items():
            v.fuente = v.fuente or ("anverso" if c == CARA_FRONTAL else "reverso")
            v.conf = round(v.conf * 0.7, 1)
            campos.setdefault(k, v)
    mrz = parsear_mrz(_lineas_mrz(lineas))
    for k, v in _campos_mrz(mrz).items():
        campos[k] = v
    return LecturaParseada(None, None, campos)


def parsear_texto(texto: str, tipo: str | None = None, cara: str | None = None) -> LecturaParseada:
    """Atajo para pruebas: parsea texto plano con posiciones sintéticas."""
    return parsear_lineas(lineas_desde_texto(texto), tipo, cara)


# --------------------------------------------------------------------------
# Votación entre pasadas
# --------------------------------------------------------------------------


def _clave_voto(campo: str, valor: str) -> str:
    if campo in ("nombres", "apellidos", "lugar_nacimiento", "ciudad_expedicion"):
        return re.sub(r"[^A-Z]", "", plano_ascii(valor))
    return valor


class Votacion:
    """Acumula candidatos de varias pasadas y elige por mayoría + confianza."""

    def __init__(self) -> None:
        self._votos: dict[str, dict[str, list[Valor]]] = {}

    def agregar(self, campos: dict[str, Valor]) -> None:
        for campo, v in campos.items():
            if not v.valor:
                continue
            grupo = self._votos.setdefault(campo, {})
            grupo.setdefault(_clave_voto(campo, v.valor), []).append(v)

    def mejor(self, campo: str) -> tuple[Valor, int] | None:
        grupo = self._votos.get(campo)
        if not grupo:
            return None

        def puntaje(valores: list[Valor]) -> tuple[float, float]:
            return (
                len(valores) + max(v.conf for v in valores) / 1000,
                max(v.conf for v in valores),
            )

        ganadores = max(grupo.values(), key=puntaje)
        # Variante a mostrar: la más votada; empate → la que trae más palabras.
        textos: dict[str, int] = {}
        for v in ganadores:
            textos[v.valor] = textos.get(v.valor, 0) + 1
        texto = max(textos, key=lambda t: (textos[t], t.count(" ")))
        conf = max(v.conf for v in ganadores)
        if len(ganadores) >= 2:
            conf = min(99.0, conf + 5 * (len(ganadores) - 1))
        fuente = ganadores[0].fuente
        return Valor(texto, round(conf, 1), fuente), len(ganadores)

    def resultado(self) -> dict[str, Valor]:
        salida = {}
        for campo in self._votos:
            elegido = self.mejor(campo)
            if elegido:
                salida[campo] = elegido[0]
        return salida

    def estable(self, campos: tuple[str, ...], minimo: int = 2) -> bool:
        """True si todos los campos esperados tienen al menos ``minimo`` votos."""
        for campo in campos:
            elegido = self.mejor(campo)
            if not elegido or elegido[1] < minimo:
                return False
        return True
