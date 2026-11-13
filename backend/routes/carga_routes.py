"""Cargues masivos de operaciones.

GET /cargas/garantias-runtpro — archivo plano .txt RNGM (default,
guía RUNTPRO GM Fase II) o Excel multi-hoja de revisión
(`formato=excel`) con las garantías mobiliarias (prendas) pendientes.
GET /cargas/garantias-runtpro/advertencias — vista previa JSON de lo
que saldría: pendientes y campos a corregir antes de generar.

Roles: admin y contabilidad (el equipo de operaciones).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual, requiere_roles
from backend.db_models.session import get_db
from backend.routes.dependencies import auditar_acceso
from backend.services.garantia_runt_service import (
    MIME_XLSX,
    GarantiaRuntService,
)
from backend.services.registro_garantias_excel_service import (
    generar_desde_excel,
)
from backend.services.rngm_plano_service import (
    MIME_TXT,
    ArchivoPlanoRngmService,
)

router = APIRouter(prefix="/cargas", tags=["cargas"])


@router.get("/garantias-runtpro")
def garantias_runtpro(
    request: Request,
    incluir_exportadas: bool = False,
    formato: Literal["txt", "excel"] = "txt",
    usuario: UsuarioActual = Depends(requiere_roles("admin", "contabilidad")),
    db: Session = Depends(get_db),
) -> Response:
    """Cargue masivo de garantías (prendas de motos) al RNGM en RUNTPRO.

    `formato=txt` (default): el archivo plano oficial de la guía GM
    Fase II — control + PRN/GRV/DEU/VEH por prenda, nombre
    `<NIT>RGM<consecutivo><AAAAMMDD>.txt`. Marca las garantías
    incluidas: un segundo clic no repite prendas (RUNTPRO rechaza
    duplicados) e `incluir_exportadas` regenera un archivo anterior.

    `formato=excel`: la hoja de revisión multi-hoja (Garantías +
    Advertencias) para depurar los datos antes del .txt; no marca.

    Headers extra: `X-Garantias-Exportadas` (prendas del archivo),
    `X-Registros` (líneas del plano, solo txt) y `X-Advertencias`
    (campos a revisar antes de radicar en RUNTPRO).
    """
    if formato == "excel":
        contenido, nombre, n_garantias, n_advertencias = GarantiaRuntService(
            db
        ).generar(incluir_exportadas=incluir_exportadas, marcar=False)
        n_registros = None
        mime = MIME_XLSX
    else:
        contenido, nombre, n_garantias, advertencias = ArchivoPlanoRngmService(
            db
        ).generar(
            incluir_exportadas=incluir_exportadas,
            generado_por=usuario.nombre,
        )
        n_advertencias = len(advertencias)
        n_registros = contenido.count(b"\n") - 1  # sin el control
        mime = MIME_TXT
    auditar_acceso(
        db,
        usuario,
        "exporta_garantias_runt",
        f"cargue garantías RUNTPRO formato={formato} "
        f"({n_garantias} garantías, incluir_exportadas={incluir_exportadas})",
        request,
    )
    db.commit()
    headers = {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "X-Garantias-Exportadas": str(n_garantias),
        "X-Advertencias": str(n_advertencias),
    }
    if n_registros is not None:
        headers["X-Registros"] = str(n_registros)
    return Response(content=contenido, media_type=mime, headers=headers)


@router.post("/garantias-runtpro/excel")
async def garantias_runtpro_excel(
    request: Request,
    archivo: Annotated[UploadFile, File()],
    hoja: Annotated[str, Form()] = "2026",
    desde: Annotated[int, Form()] = 1,
    nit: Annotated[str | None, Form()] = None,
    formato: Literal["txt", "excel"] = "txt",
    usuario: UsuarioActual = Depends(requiere_roles("admin", "contabilidad")),
    db: Session = Depends(get_db),
) -> Response:
    """Cargue masivo RNGM desde el Excel externo de registro.

    El registro operativo ("<año> Sumoto <sede> - Registro Garantia.xlsx")
    lista una garantía por fila; se toman las de `ESTADO DE PAGO =
    PENDIENTE` desde la fila `desde` de la hoja `hoja` y se genera el
    mismo plano de la guía RUNTPRO GM Fase II que el cargue por
    solicitudes (`formato=txt`, default) o su hoja de revisión
    (`formato=excel`). `nit` permite radicar con otro acreedor; por
    defecto va el NIT del aliado propio.

    El lote queda auditado en `rngm_archivo_lote` con el consecutivo del
    día — no choca con los archivos que genera la app. Headers extra:
    `X-Garantias-Exportadas`, `X-Advertencias` y `X-Revision` (nombre
    del Excel de revisión generado en el mismo lote)."""
    contenido = await archivo.read()
    txt, nombre, n_prendas, advertencias, revision, _nit, _acreedor = (
        generar_desde_excel(
            db,
            contenido=contenido,
            hoja=hoja,
            desde=desde,
            nit=nit,
            generado_por=usuario.nombre,
        )
    )
    nombre_revision = nombre.replace(".txt", "_revision.xlsx")
    auditar_acceso(
        db,
        usuario,
        "exporta_garantias_runt",
        f"cargue garantías RUNTPRO desde Excel '{archivo.filename}' "
        f"hoja={hoja} desde={desde} formato={formato} "
        f"({n_prendas} garantías)",
        request,
    )
    db.commit()
    headers = {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "X-Garantias-Exportadas": str(n_prendas),
        "X-Advertencias": str(len(advertencias)),
        "X-Revision": nombre_revision,
    }
    if formato == "excel":
        return Response(
            content=revision,
            media_type=MIME_XLSX,
            headers={**headers, "Content-Disposition":
                     f'attachment; filename="{nombre_revision}"'},
        )
    return Response(content=txt, media_type=MIME_TXT, headers=headers)


@router.get("/garantias-runtpro/advertencias")
def advertencias_runtpro(
    request: Request,
    incluir_exportadas: bool = False,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "contabilidad")),
    db: Session = Depends(get_db),
) -> dict:
    """Vista previa del cargue sin marcar ni generar archivo.

    `pendientes` son las prendas que entrarían al .txt ahora; cada
    advertencia es un campo que RUNTPRO exige y hoy va vacío o sin
    mapear (VIN, género, DANE del municipio, monto…)."""
    pendientes, advertencias = ArchivoPlanoRngmService(
        db
    ).advertencias_pendientes(incluir_exportadas=incluir_exportadas)
    auditar_acceso(
        db,
        usuario,
        "consulta_advertencias_runt",
        f"vista previa cargue RUNTPRO ({pendientes} pendientes)",
        request,
    )
    db.commit()
    return {
        "pendientes": pendientes,
        "advertencias": [
            {
                "num_solicitud": a[0],
                "cliente": a[1],
                "cedula": a[2],
                "mensaje": a[3],
            }
            for a in advertencias
        ],
    }
