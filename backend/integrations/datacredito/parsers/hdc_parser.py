"""Parser de respuesta JSON de Historia de Credito+ REST a modelos de dominio."""

from datetime import date, datetime
from typing import Any

from backend.integrations.datacredito.parsers.common import _dec, _int, _str
from backend.models.buro_models import (
    Alerta,
    CuentaAhorro,
    CuentaCartera,
    CuentaCorriente,
    EndeudamientoGlobal,
    PersonaBasica,
    Quanto,
    RespuestaHDC,
    Score,
    TarjetaCredito,
)

_CALIFICACIONES_OBLIGACION = {
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "D",
    "5": "E",
    "6": "AA",
    "7": "BB",
    "8": "CC",
    "9": "K",
}


def _calificacion_obligacion(account: dict[str, Any], value: dict[str, Any]) -> tuple[str | None, str | None]:
    """Tabla 14 HDC+: prioriza la calificación actual de la cuenta sobre el histórico."""
    rating = _str(account.get("rating")) or _str(value.get("rating"))
    rating_desc = _str(account.get("ratingDesc")) or _str(value.get("ratingDesc"))
    normalizado = str(rating or "").strip().upper()
    return _CALIFICACIONES_OBLIGACION.get(normalizado, rating), rating_desc


def _date(value: Any) -> date | None:
    if not value or value == "-1":
        return None
    if isinstance(value, (int, float)):
        # Timestamp en milisegundos
        try:
            return datetime.fromtimestamp(value / 1000).date()
        except (ValueError, OSError):
            return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


class HDCParser:
    """Parsea el JSON de HDC+ devuelto por el servicio REST."""

    def parse(self, payload: dict[str, Any]) -> RespuestaHDC:
        # El servicio envuelve todo en 'ReportHDCplus'
        root = payload.get("ReportHDCplus", payload)

        respuesta = RespuestaHDC()

        # Codigo y descripcion de respuesta
        product_result = root.get("productResult", {})
        respuesta.respuesta_codigo = str(product_result.get("responseCode", ""))
        respuesta.respuesta_desc = product_result.get("responseDesc", "")

        # Persona basica
        respuesta.persona = self._parse_persona(root)

        # Scores
        respuesta.scores = self._parse_scores(root)

        # Quanto
        respuesta.quanto = self._parse_quanto(root)

        # Cuentas
        respuesta.cuentas_cartera = self._parse_cuentas_cartera(root)
        respuesta.tarjetas_credito = self._parse_tarjetas(root)
        respuesta.cuentas_ahorro = self._parse_cuentas_ahorro(root)
        respuesta.cuentas_corriente = self._parse_cuentas_corriente(root)

        # Endeudamiento global
        respuesta.endeudamiento_global = self._parse_endeudamiento(root)

        # Alertas
        respuesta.alertas = self._parse_alertas(root)

        return respuesta

    # -----------------------------------------------------------
    # PARSERS INTERNOS
    # -----------------------------------------------------------
    def _parse_persona(self, root: dict[str, Any]) -> PersonaBasica | None:
        basic = root.get("basicInformation", {})
        if not isinstance(basic, dict):
            basic = {}
        natural = None
        location = root.get("location", {})
        if isinstance(location, dict) and isinstance(location.get("nationalNatural"), dict):
            natural = location["nationalNatural"]
        elif isinstance(root.get("nationalNatural"), dict):
            natural = root["nationalNatural"]
        elif basic:
            # El JSON que se descarga desde el portal puede usar basicInformation
            # en lugar de location.nationalNatural.
            natural = basic

        if not natural:
            return None

        ident = natural.get("identification", {})
        person_id = ident.get("personId", {}) if isinstance(ident, dict) else {}
        if not person_id and isinstance(natural.get("personId"), dict):
            person_id = natural["personId"]
        # Algunas respuestas mezclan location.nationalNatural con
        # basicInformation/identifyingAttributes para completar el documento.
        basic_ident = basic.get("identification", {})
        basic_person_id = basic_ident.get("personId", {}) if isinstance(basic_ident, dict) else {}
        if not isinstance(person_id, dict):
            person_id = {}
        for key in ("personIdType", "personIdNumber"):
            if not person_id.get(key) and isinstance(basic_person_id, dict):
                person_id[key] = basic_person_id.get(key)
            identifying = root.get("identifyingAttributes", {})
            identifying_person_id = identifying.get("personId", {}) if isinstance(identifying, dict) else {}
            if not person_id.get(key) and isinstance(identifying_person_id, dict):
                person_id[key] = identifying_person_id.get(key)
        age = natural.get("age", {})

        return PersonaBasica(
            nombres=natural.get("names"),
            primer_apellido=natural.get("firstLastName"),
            segundo_apellido=natural.get("secondLastName"),
            nombre_completo=natural.get("fullName"),
            tipo_id=str(person_id.get("personIdType", "")) or None,
            numero_id=str(person_id.get("personIdNumber", "")) or None,
            genero=str(natural.get("gender", "")) or None,
            estado_documento=_str(ident.get("statusId")) if isinstance(ident, dict) else None,
            validada=bool(natural.get("officialSourceValidationStatus", False)),
            rut=bool(natural.get("citizenTaxRegistrationIndicator", False)),
            edad_min=_int(age.get("min")) if age else None,
            edad_max=_int(age.get("max")) if age else None,
        )

    def _parse_scores(self, root: dict[str, Any]) -> list[Score]:
        scores = []
        for item in root.get("models", []) or []:
            score_value = item.get("scoreValue")
            razones = []
            for r in item.get("ScoreReason", []) or []:
                if isinstance(r, dict) and r.get("reason"):
                    razones.append(str(r["reason"]))
                elif isinstance(r, str):
                    razones.append(r)
            scores.append(
                Score(
                    tipo=str(item.get("modelCode", "")) or None,
                    # Un score numérico 0 es válido para reglas de exclusión;
                    # no debe confundirse con un campo ausente.
                    puntaje=(_dec(score_value) if score_value is not None and score_value != "" else None),
                    razones=razones,
                    fecha=_date(item.get("modelDate")),
                    poblacion=_int(item.get("population")) if item.get("population") else None,
                )
            )
        return scores

    def _parse_quanto(self, root: dict[str, Any]) -> Quanto | None:
        # El JSON de HDC+ REST suele traer productosValores como lista
        productos = root.get("productValueList") or root.get("productosValores")
        if not productos:
            return None
        # Algunos PDF/serializadores envuelven el arreglo una vez mas: [[{...}]].
        if isinstance(productos, list) and len(productos) == 1 and isinstance(productos[0], list):
            productos = productos[0]

        # Buscar producto 62 (Quanto) o 04 (Quanto-V3)
        for p in productos:
            if not isinstance(p, dict):
                continue
            codigo = str(p.get("productCode") or p.get("producto") or "")
            if codigo in ("62", "04"):
                return Quanto(
                    producto=codigo,
                    valor_medio=_dec(p.get("value") or p.get("valor1")),
                    valor_min=_dec(p.get("value2") or p.get("valor2")),
                    valor_max=_dec(p.get("value3") or p.get("valor3")),
                    valor_medio_smlv=_dec(p.get("valueSMLV") or p.get("valor1sm1v")),
                    valor_min_smlv=_dec(p.get("value2SMLV") or p.get("valor2sm1v")),
                    valor_max_smlv=_dec(p.get("value3SMLV") or p.get("valor3sm1v")),
                    razon=str(p.get("reason") or p.get("razon1") or "") or None,
                )
        return None

    def _parse_cuentas_cartera(self, root: dict[str, Any]) -> list[CuentaCartera]:
        cuentas = []
        for c in root.get("liabilities") or root.get("CuentaCartera") or []:
            if not isinstance(c, dict):
                continue
            account = c.get("account") if isinstance(c.get("account"), dict) else c
            features = c.get("features") or c.get("featuresLiabilities") or {}
            if not isinstance(features, dict):
                features = {}
            values_list = c.get("values", [])
            v = values_list[0] if values_list and isinstance(values_list[0], dict) else {}
            status = c.get("status", {}) if isinstance(c.get("status"), dict) else {}
            account_status = status.get("account", {}) if isinstance(status.get("account"), dict) else {}
            origin_status = status.get("origin", {}) if isinstance(status.get("origin"), dict) else {}
            payment_status = status.get("payment", {}) if isinstance(status.get("payment"), dict) else {}
            liabilities_account = c.get("liabilitiesAccount", {})
            if not isinstance(liabilities_account, dict):
                liabilities_account = {}
            account_type = (
                features.get("accountTypeDesc")
                or account.get("accountTypeDesc")
                or account.get("subAccountTypeDesc")
                or account.get("subAccountTypeName")
            )
            estado_origen_desc = (
                origin_status.get("originStatusOfAccountDesc")
                or origin_status.get("originStatusDesc")
                or origin_status.get("statusDescription")
            )
            estado_cuenta_desc = (
                account_status.get("businessAccountStatusDesc")
                or account_status.get("businessAccountStatusDescription")
                or account_status.get("statusDescription")
            )
            comportamiento = liabilities_account.get("businessBehaviourVectorProduct")
            calificacion, calificacion_desc = _calificacion_obligacion(account, v)

            cuentas.append(
                CuentaCartera(
                    entidad=_str(account.get("businessLineName") or account.get("businessLineCode")),
                    numero=str(account.get("accountNumber", "")) or None,
                    tipo_cuenta=_str(account_type),
                    calificacion=calificacion,
                    calificacion_desc=calificacion_desc,
                    estado_pago=_str(account_status.get("businessAccountStatus")),
                    estado_cuenta=_str(account_status.get("businessAccountStatus")),
                    estado_cuenta_desc=_str(estado_cuenta_desc),
                    estado_origen=_str(origin_status.get("originStatusOfAccount")),
                    estado_origen_desc=_str(estado_origen_desc),
                    fecha_estado_origen=_date(origin_status.get("dateOfOriginStatus")),
                    evento_buro=_str(payment_status.get("businessBureauEvent")),
                    fecha_evento=_date(payment_status.get("paymentDate") or account_status.get("accountStatusDate")),
                    fecha_actualizacion=_date(account_status.get("accountStatusDate")),
                    fecha_apertura=_date(account.get("accountOpeningDate")),
                    fecha_vencimiento=_date(liabilities_account.get("expiryDate")),
                    saldo_actual=_dec(v.get("debtBalance")),
                    saldo_mora=_dec(v.get("businessValueBalanceOverdue")),
                    cuota=_dec(v.get("valueMonthlyPayment")),
                    valor_inicial=_dec(v.get("initialValue")),
                    dias_mora=_int(v.get("delinquencyMaturation")),
                    cuotas_mora=_int(v.get("installmentsOverdue")),
                    comportamiento=str(comportamiento).strip() if comportamiento else None,
                    sector=str(account.get("economicSector", "")) or None,
                    bloqueada=bool(account.get("block", False)),
                    forma_pago=_str(v.get("periodicityOfPaymentsDesc") or v.get("periodicityOfPayments")),
                    calidad_deudor=_str(features.get("typeOfDebtorDesc") or features.get("typeOfDebtor")),
                )
            )
        return cuentas

    def _parse_tarjetas(self, root: dict[str, Any]) -> list[TarjetaCredito]:
        tarjetas = []
        for c in root.get("CreditCardList") or root.get("creditCard") or root.get("TarjetaCredito") or []:
            if not isinstance(c, dict):
                continue
            account = c.get("account") if isinstance(c.get("account"), dict) else c
            features = c.get("features") or c.get("FeaturesCreditCard") or {}
            if not isinstance(features, dict):
                features = {}
            values_list = c.get("values", [])
            v = values_list[0] if values_list and isinstance(values_list[0], dict) else {}
            status = c.get("status", {}) if isinstance(c.get("status"), dict) else {}
            account_status = status.get("account", {}) if isinstance(status.get("account"), dict) else {}
            origin_status = status.get("origin", {}) if isinstance(status.get("origin"), dict) else {}
            payment_status = status.get("payment", {}) if isinstance(status.get("payment"), dict) else {}
            card_status = status.get("card", {}) if isinstance(status.get("card"), dict) else {}
            card_account = c.get("creditCardAccount", {})
            if not isinstance(card_account, dict):
                card_account = {}
            comportamiento = card_account.get("businessBehaviourVectorProduct")
            estado_origen_desc = (
                origin_status.get("originStatusOfAccountDesc")
                or origin_status.get("originStatusDesc")
                or origin_status.get("statusDescription")
            )
            estado_cuenta_desc = (
                account_status.get("businessAccountStatusDesc")
                or account_status.get("businessAccountStatusDescription")
                or account_status.get("statusDescription")
            )
            calificacion, calificacion_desc = _calificacion_obligacion(account, v)

            tarjetas.append(
                TarjetaCredito(
                    entidad=_str(account.get("businessLineName") or account.get("businessLineCode")),
                    numero=str(account.get("accountNumber", "")) or None,
                    calificacion=calificacion,
                    calificacion_desc=calificacion_desc,
                    estado_pago=_str(account_status.get("businessAccountStatus")),
                    estado_cuenta=_str(origin_status.get("originStatusOfAccount")),
                    estado_cuenta_desc=_str(estado_cuenta_desc),
                    estado_plastico=_str(card_status.get("cardStatusCode")),
                    evento_buro=_str(payment_status.get("businessBureauEvent")),
                    estado_origen=_str(origin_status.get("originStatusOfAccount")),
                    estado_origen_desc=_str(estado_origen_desc),
                    fecha_estado_origen=_date(origin_status.get("dateOfOriginStatus")),
                    fecha_apertura=_date(account.get("accountOpeningDate")),
                    fecha_vencimiento=_date(card_account.get("expiryDate")),
                    fecha_evento=_date(payment_status.get("paymentDate") or account_status.get("accountStatusDate")),
                    fecha_actualizacion=_date(account_status.get("accountStatusDate")),
                    saldo_actual=_dec(v.get("debtBalance")),
                    saldo_mora=_dec(v.get("businessValueBalanceOverdue")),
                    cupo_total=_dec(v.get("initialValue")),
                    cuota=_dec(v.get("valueMonthlyPayment")),
                    dias_mora=_int(v.get("delinquencyMaturation")),
                    cuotas_mora=_int(v.get("installmentsOverdue")),
                    comportamiento=str(comportamiento).strip() if comportamiento else None,
                    sector=str(account.get("economicSector", "")) or None,
                    bloqueada=bool(account.get("block", False)),
                    franquicia=_str(features.get("FranchiseType") or features.get("franchiseName")),
                    clase=_str(features.get("cardClass") or features.get("cardClassName")),
                    forma_pago=_str(v.get("periodicityOfPaymentsDesc") or v.get("periodicityOfPayments")),
                    calidad_deudor=_str(features.get("typeOfDebtorDesc") or features.get("typeOfDebtor")),
                )
            )
        return tarjetas

    def _parse_cuentas_ahorro(self, root: dict[str, Any]) -> list[CuentaAhorro]:
        cuentas = []
        for c in root.get("savings", []) or root.get("CuentaAhorro", []):
            if not isinstance(c, dict):
                continue
            account = c.get("account") if isinstance(c.get("account"), dict) else c
            status = c.get("status", {}) if isinstance(c.get("status"), dict) else {}
            status_value = status.get("businessBureauEvent") or status.get("businessAccountStatus")
            if not status_value and isinstance(status.get("account"), dict):
                status_value = status["account"].get("businessAccountStatus")
            if not status_value and isinstance(status.get("payment"), dict):
                status_value = status["payment"].get("businessBureauEvent")
            cuentas.append(
                CuentaAhorro(
                    entidad=_str(account.get("businessLineName") or account.get("businessLineCode")),
                    numero=str(account.get("accountNumber", "")) or None,
                    calificacion=_str(account.get("rating")),
                    estado=_str(status_value),
                    fecha_apertura=_date(account.get("accountOpeningDate")),
                    bloqueada=bool(account.get("block", False)),
                )
            )
        return cuentas

    def _parse_cuentas_corriente(self, root: dict[str, Any]) -> list[CuentaCorriente]:
        cuentas = []
        for c in root.get("checkingList", []) or root.get("CuentaCorriente", []):
            if not isinstance(c, dict):
                continue
            account = c.get("account") if isinstance(c.get("account"), dict) else c
            status = c.get("status", {}) if isinstance(c.get("status"), dict) else {}
            status_value = status.get("businessBureauEvent") or status.get("businessAccountStatus")
            if not status_value and isinstance(status.get("account"), dict):
                status_value = status["account"].get("businessAccountStatus")
            if not status_value and isinstance(status.get("payment"), dict):
                status_value = status["payment"].get("businessBureauEvent")
            cuentas.append(
                CuentaCorriente(
                    entidad=_str(account.get("businessLineName") or account.get("businessLineCode")),
                    numero=str(account.get("accountNumber", "")) or None,
                    calificacion=_str(account.get("rating")),
                    estado=_str(status_value),
                    fecha_apertura=_date(account.get("accountOpeningDate")),
                    bloqueada=bool(account.get("block", False)),
                )
            )
        return cuentas

    def _parse_endeudamiento(self, root: dict[str, Any]) -> list[EndeudamientoGlobal]:
        out = []
        for e in root.get("globalIndebtedness", []) or root.get("EndeudamientoGlobal", []):
            entidad = e.get("entity", {})
            out.append(
                EndeudamientoGlobal(
                    entidad=entidad.get("businessLineName") if isinstance(entidad, dict) else None,
                    sector=str(entidad.get("economicSector", "")) if isinstance(entidad, dict) else None,
                    calificacion=_str(e.get("quarterQualification")),
                    tipo_credito=_str(e.get("typeOfCredit")),
                    moneda=_str(e.get("currencyType")),
                    numero_creditos=_int(e.get("quantityOfObligations")),
                    saldo_pendiente=_dec(e.get("capitalValue")),
                    fecha_reporte=_date(e.get("cutoffDate")),
                )
            )
        return out

    def _parse_alertas(self, root: dict[str, Any]) -> list[Alerta]:
        out = []
        for a in root.get("alerts", []) or root.get("Alerta", []):
            source = a.get("source", {})
            out.append(
                Alerta(
                    codigo=str(a.get("alertCode", "")) or None,
                    texto=a.get("textAlert"),
                    fuente=source.get("sourceDescription") if isinstance(source, dict) else None,
                    colocacion=_date(a.get("alertDate")),
                    vencimiento=_date(a.get("alertExpiryDate")),
                )
            )
        return out


# Alias por compatibilidad con el nombre original.
HDCparser = HDCParser
