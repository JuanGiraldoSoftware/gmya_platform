"""Pantalla "Programacion de pagos" (Streamlit). Contrato: modulo_prog_pagos().

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.cache, gmya.comun.config_equipo, gmya.ui.componentes, gmya.ui.visor, gmya.modulos.pagos.lectura, gmya.modulos.pagos.reglas, gmya.modulos.pagos.excel, gmya.modulos.pagos.medfam, gmya.ui.interfaz_comun, gmya.registro.interfaz
"""

import datetime
import html
import re
from pathlib import Path

import streamlit as st

from gmya.comun.texto import comparable
from gmya.comun.numeros import formato_cop
from gmya.comun.cache import _cache_datos, _huella
from gmya.comun.config_equipo import leer_config
from gmya.ui.componentes import (
    banner_modulo, encabezado_carga, _glosario_pp, titulo_seccion,
)
from gmya.ui.visor import contenido_tabla_visor
from gmya.modulos.pagos.lectura import (
    empresa_implementada, empresas_para_selector, EMPRESAS_PROG_PAGOS,
    fechas_pago_sugeridas, leer_conceptos_helisa, leer_prog_anterior,
    leer_programacion_helisa,
)
from gmya.modulos.pagos.reglas import armar_prog_pagos, orden_partidas
from gmya.modulos.pagos.excel import (
    generar_excel_prog_pagos, marcas_revision_pp, nombre_archivo_prog,
    resumen_prog_pagos,
)
from gmya.modulos.pagos.medfam import (
    armar_cxp_medfam, comparar_seguridad_social, generar_excel_cxp,
    groupby_proveedor, leer_cxp_anterior, leer_cxp_helisa,
    nombre_archivo_cxp, orden_cxp, resumen_cxp,
)
from gmya.ui.interfaz_comun import _filtro_visor, _mostrar_visor
from gmya.registro.interfaz import reportar_error


# ============================================================
# INTERFAZ: PROGRAMACION DE PAGOS
# ============================================================
CSS_PROG_PAGOS = """
<style>
.gm-emp-off {
    position: relative; display: flex; align-items: center; gap: .5rem;
    min-height: 2.6rem; padding: .45rem .8rem; margin-bottom: .55rem;
    border-radius: .5rem; border: 1px dashed #C9C2C6;
    background: #F4F1F3; color: #A39BA0 !important; font-size: .86rem;
    font-weight: 600; cursor: not-allowed; outline: none;
}
.gm-emp-off .gm-emp-nombre { flex: 1; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap; }
.gm-emp-off .gm-emp-candado {
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%; flex: 0 0 22px;
    border: 2px solid #C9C2C6; color: #A39BA0; font-size: .75rem;
    font-weight: 900; background: #fff;
}
.gm-emp-off .gm-ayuda-texto {
    visibility: hidden; opacity: 0; position: absolute; top: calc(100% + 6px);
    left: 0; z-index: 9999; width: min(320px, 80vw);
    background: var(--gm-tinta); color: var(--gm-blanco) !important;
    border: 2px solid var(--gm-magenta); border-radius: 12px;
    padding: .7rem .9rem; font-size: .78rem; font-weight: 500;
    line-height: 1.5; box-shadow: 5px 5px 0 var(--gm-magenta);
    white-space: normal; cursor: default;
}
.gm-emp-off .gm-ayuda-texto b { color: var(--gm-magenta-claro); }
.gm-emp-off:hover .gm-ayuda-texto,
.gm-emp-off:focus .gm-ayuda-texto { visibility: visible; opacity: 1; }
.gm-glosario { display: flex; flex-wrap: wrap; align-items: center;
    gap: .45rem; margin: .2rem 0 .7rem; }
.gm-glo-tit { font-size: .74rem; font-weight: 900; letter-spacing: .1em;
    text-transform: uppercase; color: var(--gm-carbon); margin-right: .2rem; }
.gm-glo-chip { display: inline-flex; align-items: center; gap: .35rem;
    background: var(--gm-blanco); border: 2px solid var(--gm-carbon);
    border-radius: 999px; padding: .15rem .25rem .15rem .7rem;
    font-size: .78rem; font-weight: 800; color: var(--gm-carbon); }
.gm-glo-chip .gm-ayuda { margin-left: .1rem; width: 20px; height: 20px;
    flex: 0 0 20px; font-size: .72rem; }
</style>
"""

DIAS_PP = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

TIP_NO_IMPLEMENTADA = (
    "<b>Aún no implementado.</b> La programación de pagos de esta empresa "
    "todavía no está configurada en la plataforma. Cuando se configure "
    "(con su programación anterior y sus informes de HELISA de ejemplo) "
    "quedará disponible aquí.")


def _ficha_no_implementada(nombre):
    st.markdown(
        f'<div class="gm-emp-off" tabindex="0">'
        f'<span class="gm-emp-candado">–</span>'
        f'<span class="gm-emp-nombre">{html.escape(nombre)}</span>'
        f'<span class="gm-ayuda-texto">{TIP_NO_IMPLEMENTADA}</span></div>',
        unsafe_allow_html=True)


def _elegir_empresa_pp(nombre, clave):
    if st.session_state.get("pp_empresa") == clave:
        # Clic sobre la empresa ya elegida: se quita la seleccion.
        st.session_state.pop("pp_empresa", None)
        st.session_state.pop("pp_empresa_nombre", None)
    else:
        st.session_state["pp_empresa"] = clave
        st.session_state["pp_empresa_nombre"] = nombre
    for llave in ("pp_huella", "pp_partidas", "pp_archivo"):
        st.session_state.pop(llave, None)


def _selector_empresas_pp():
    st.markdown(CSS_PROG_PAGOS, unsafe_allow_html=True)
    actual = st.session_state.get("pp_empresa")
    if actual in EMPRESAS_PROG_PAGOS:
        # Con una empresa elegida solo se muestra esa; un clic sobre ella
        # la deselecciona y vuelve a mostrar todas.
        nombre = st.session_state.get("pp_empresa_nombre") or \
            EMPRESAS_PROG_PAGOS[actual]["nombre"]
        c1, c2 = st.columns([1, 2])
        with c1:
            st.button(f"✓ {nombre}", key="pp_emp_actual", type="primary",
                      on_click=_elegir_empresa_pp, args=(nombre, actual),
                      use_container_width=True,
                      help="Haz clic para quitar la selección y ver todas "
                           "las empresas.")
        with c2:
            st.caption("Empresa seleccionada. Haz clic sobre ella para "
                       "quitar la selección y volver a ver todas las "
                       "empresas.")
        return
    config = leer_config()
    carpeta = config.get("ruta_empresas") or ""
    try:
        carpeta = carpeta if carpeta and Path(carpeta).is_dir() else ""
    except OSError:
        carpeta = ""
    empresas = empresas_para_selector(carpeta)
    implementadas = sum(1 for _, c in empresas if c)
    if carpeta:
        st.caption(f"{len(empresas)} empresas de la carpeta "
                   f"«{Path(carpeta).name}» · {implementadas} con la "
                   "programación implementada. Las que están en gris aún no "
                   "se pueden seleccionar (pasa el cursor para ver por qué).")
    else:
        st.caption("Para ver aquí todas las empresas, configura la carpeta "
                   "«001. EMPRESAS ACTIVAS USO DIARIO» en el módulo Búsqueda "
                   "de archivos (solo se lee la lista de carpetas).")
    filtro = ""
    if len(empresas) > 12:
        filtro = st.text_input("Buscar empresa", key="pp_filtro_empresa",
                               placeholder="Escribe parte del nombre…")
    visibles = [(n, c) for n, c in empresas
                if not filtro or comparable(filtro) in comparable(n)]
    # Las implementadas primero, luego el resto en orden alfabetico.
    visibles.sort(key=lambda x: (x[1] is None, comparable(x[0])))
    columnas = st.columns(3)
    for i, (nombre, clave) in enumerate(visibles):
        with columnas[i % 3]:
            if clave:
                st.button(nombre, key=f"pp_emp_{i}_{clave}",
                          type="secondary", on_click=_elegir_empresa_pp,
                          args=(nombre, clave), use_container_width=True,
                          help="Programación de pagos implementada.")
            else:
                _ficha_no_implementada(nombre)
    if not visibles:
        st.info("Ninguna empresa coincide con la búsqueda.")


def _visor_revision_pp(partidas, ordenar, ant_titulo, tabla_ant, hel_titulo,
                       tabla_hel, clave, explicacion_extra=""):
    titulo_seccion(
        "Visor de revisión", 5,
        "Muestra la <b>programación anterior</b> y el informe de "
        "<b>HELISA</b> completos, cada uno con su desplazamiento y el número "
        "de fila del archivo. Se marcan (número y color) solo las partidas "
        "que <b>se están incluyendo</b> pero conviene confirmar: si siguen "
        "vigentes, si el valor es correcto o si se deben seguir pasando. "
        "Pasa el mouse sobre una fila marcada para ver qué revisar. "
        "<b>Siguiente ▶</b> salta a la próxima marca en ese documento; "
        "<b>Ctrl + rueda</b> hace zoom." + explicacion_extra)
    marcas_a, marcas_h, tips, leyenda = marcas_revision_pp(partidas, ordenar)
    if not leyenda:
        st.success("No hay partidas incluidas que requieran revisión "
                   "especial.")
        return
    solo = _filtro_visor(f"{clave}_visor_filtro")
    with st.expander(f"Leyenda ({len(leyenda)} partidas por revisar)",
                     expanded=False):
        st.dataframe(leyenda, use_container_width=True, hide_index=True)

    def panel(codigo, titulo, tabla, marcas):
        return {"codigo": codigo,
                "titulo": f"{titulo} · {len(marcas)} filas marcadas",
                "contenido": contenido_tabla_visor(tabla, marcas, tips,
                                                   solo)}
    _mostrar_visor([panel("ANT", ant_titulo, tabla_ant, marcas_a),
                    panel("HELISA", hel_titulo, tabla_hel, marcas_h)])


@_cache_datos
def _leer_entradas_pp(prog_bytes, conc_bytes, ant_bytes, ant_nombre):
    return (leer_programacion_helisa(prog_bytes),
            leer_conceptos_helisa(conc_bytes),
            leer_prog_anterior(ant_bytes, ant_nombre))


def _etiqueta_fecha_pp(f):
    return f"Pagos al {f:%d/%m/%Y}"


def _tabla_revision_pp(partidas, fechas_pago, mostrar_todas):
    import pandas as pd
    opciones = ["Sin programar"] + [_etiqueta_fecha_pp(f)
                                    for f in fechas_pago]
    filas = []
    for p in orden_partidas(partidas):
        if not mostrar_todas and not p["incluir"]:
            continue
        i = p.get("programar")
        filas.append({
            "id": p["id"],
            "Incluir": bool(p["incluir"]),
            "Sección": {"factura": "Factura", "anticipo": "Anticipo",
                        "fijo": "Pago fijo"}[p["seccion"]],
            "Proveedor / grupo": p.get("proveedor") or p.get("grupo") or "",
            "Número": p.get("numero") or "",
            "Concepto": p.get("concepto") or "",
            "Saldo": float(p.get("saldo") or 0),
            "Programar": opciones[i + 1] if i is not None and
            0 <= i < len(fechas_pago) else opciones[0],
            "Observaciones": p.get("obs") or "",
            "Origen": p.get("origen") or "",
            "Motivo": p.get("motivo") or "",
        })
    tabla = pd.DataFrame(filas).set_index("id") if filas else None
    return tabla, opciones


def _aplicar_revision_pp(partidas, editada, opciones):
    por_id = {p["id"]: p for p in partidas}
    for ident, fila in editada.iterrows():
        p = por_id.get(ident)
        if p is None:
            continue
        p["incluir"] = bool(fila["Incluir"])
        p["concepto"] = str(fila["Concepto"] or "")
        p["obs"] = str(fila["Observaciones"] or "")
        try:
            k = opciones.index(fila["Programar"])
        except ValueError:
            k = 0
        p["programar"] = None if k == 0 else k - 1


GLOSARIO_NATURE = [
    ("Incluir",
     "Marca si la partida <b>entra en la nueva programación</b>. Incluirla "
     "significa que es una <b>obligación vigente por pagar</b> (cuenta por "
     "pagar a un proveedor, un anticipo o un pago fijo) que se presenta "
     "para aprobación: su <b>Saldo Total</b> queda en el archivo y, si se "
     "le asigna fecha, suma al <b>Gran Total</b> de esa fecha y reduce la "
     "<b>DIFERENCIA (saldo en bancos)</b>. Desmárcala si ya se pagó, se "
     "anuló, se cruzó con una nota crédito o no corresponde a la empresa."),
    ("Sección",
     "<b>Factura</b>: cuenta por pagar registrada en HELISA (2205 "
     "proveedores, 2335 costos y gastos por pagar…). <b>Anticipo</b>: pago "
     "que se gira antes de recibir la factura; luego se legaliza contra "
     "ella. <b>Pago fijo</b>: obligaciones recurrentes del flujo de caja "
     "(nómina y seguridad social, arriendos, impuestos, leasing, "
     "servicios)."),
    ("Número",
     "Documento soporte tal como está en HELISA (FC factura de compra, DSE "
     "documento soporte de adquisiciones a no obligados a facturar, CC…). "
     "Las proyecciones no tienen número porque la factura aún no llega."),
    ("Concepto",
     "Descripción del costo o gasto que se paga (columna CONCEPTO). Las "
     "facturas que ya estaban conservan el texto de la programación "
     "anterior; las nuevas traen el texto capturado en HELISA. Puedes "
     "corregirlo."),
    ("Saldo",
     "<b>Saldo por pagar</b> = valor del documento − abonos realizados "
     "(columna Saldo Total). Es el valor que se programa; con abonos el "
     "concepto empieza por «SALDO,»."),
    ("Programar",
     "Fecha de pago (columna «Pagos al…») en la que sale el saldo del "
     "<b>flujo de caja</b>. «Sin programar» deja la deuda visible en Saldo "
     "Total pero sin consumir caja en ninguna fecha (p. ej. facturas "
     "retenidas por nota crédito o por aprobar)."),
    ("Observaciones",
     "Nota para tesorería y quien aprueba el pago (reintegros, retenciones, "
     "notas crédito pendientes). Va en la columna OBSERVACIONES en rojo."),
    ("Origen",
     "De dónde sale la partida: <b>HELISA</b> (pendiente en el informe), "
     "<b>HELISA · nueva</b> (no estaba en la anterior), <b>Programación "
     "anterior</b>, <b>Proyección</b> (factura mensual que aún no llega) o "
     "<b>Pago fijo</b> (corrido al mes siguiente o con saldo)."),
    ("Motivo",
     "Por qué la plataforma sugiere incluirla o sacarla y con qué fecha. Si "
     "la partida además aparece marcada en el visor, allí está lo que "
     "conviene confirmar."),
]

GLOSARIO_CXP = [
    ("Incluir",
     "Marca si el documento <b>entra en la programación</b>. Incluirlo "
     "significa que es una <b>cuenta por pagar vigente</b> del proveedor "
     "según HELISA: su valor suma al <b>Total a pagar</b> del proveedor y "
     "al total <b>CUENTAS PENDIENTES POR PAGAR</b>. Desmárcalo si se cruza "
     "con una nota crédito, es un saldo de centavos o ya no corresponde."),
    ("Documento",
     "Tipo y número del documento en HELISA: <b>FCC</b> factura de compra, "
     "<b>DSEC</b> documento soporte (cuenta de cobro de no obligados a "
     "facturar), <b>CC</b> comprobante contable, <b>NDC</b> nota crédito, "
     "<b>PE</b> pago/egreso parcial (valor negativo)."),
    ("Vence / Días",
     "Fecha de vencimiento del documento y días de mora a la fecha de la "
     "programación (0 si aún no vence). Sirve para priorizar pagos y para "
     "las observaciones de «FACTURA VENCIDA»."),
    ("Saldo HELISA",
     "Saldo por pagar del documento en el listado de HELISA (lo que se le "
     "debe al proveedor). Los negativos (pagos parciales, notas) restan "
     "del total del proveedor."),
    ("Lo que se paga",
     "Valor que se programa pagar al proveedor (columna LO QUE SE PAGA). "
     "Por defecto es el saldo total; si se acordó un <b>abono parcial</b> "
     "(p. ej. «se recomienda ir abonando»), escribe aquí el valor del "
     "abono: el saldo restante seguirá apareciendo en HELISA."),
    ("Observaciones",
     "Nota del equipo para el proveedor o la factura (vencida, acuerdo de "
     "pago, cruces). Se conservan de la programación anterior y se "
     "escriben en rojo."),
    ("Origen",
     "<b>HELISA</b>: ya estaba en la programación anterior. <b>HELISA · "
     "nueva</b>: aparece por primera vez. <b>Programación anterior</b>: "
     "estaba antes y ya no está en HELISA (se pagó o se anuló)."),
    ("Motivo",
     "Por qué la plataforma sugiere incluirlo o no. Lo que conviene "
     "confirmar aparece además marcado en el visor."),
]


def modulo_prog_pagos():
    banner_modulo(
        "Módulo 4 · Tesorería",
        "Programación de pagos",
        "Arma la programación de pagos de cada empresa a partir de lo que "
        "sale de HELISA y de la última programación hecha: conserva los "
        "textos y observaciones ya revisados, actualiza lo pendiente y deja "
        "todo listo para revisar antes de descargar.",
        ("Por empresa", "HELISA + programación anterior",
         "Salida: Excel listo para tesorería"),
    )

    titulo_seccion(
        "Empresa", 1,
        "Escoge la empresa. Solo se pueden seleccionar las que tienen la "
        "programación <b>implementada</b>; las demás aparecen en gris. Al "
        "elegir una se ocultan las demás: haz clic otra vez sobre ella para "
        "quitar la selección. La lista sale de las carpetas de <b>001. "
        "EMPRESAS ACTIVAS USO DIARIO</b> (solo se lee, nunca se escribe en "
        "ella).")
    _selector_empresas_pp()
    clave = st.session_state.get("pp_empresa")
    if not clave or clave not in EMPRESAS_PROG_PAGOS:
        st.info("Selecciona una empresa para continuar.")
        return
    empresa = EMPRESAS_PROG_PAGOS[clave]
    if empresa.get("formato") == "cxp":
        _flujo_cxp(clave, empresa)
    else:
        _flujo_flujo_caja(clave, empresa)


def _flujo_flujo_caja(clave, empresa):
    """Programacion con flujo de caja (NATURE)."""
    nombre_empresa = empresa["nombre"]
    titulo_seccion(
        "Archivos", 2,
        "Los tres son <b>obligatorios</b>. Los dos informes de HELISA se "
        "cargan <b>tal como se descargan</b> (Excel 97-2003). La "
        "programación anterior es el último archivo PROG. PAGOS de la "
        "empresa (.xls o .xlsx): de ella se toman los textos, observaciones, "
        "fechas de pago, pagos fijos y las partidas que siguen pendientes.")
    c1, c2, c3 = st.columns(3)
    with c1:
        encabezado_carga(
            "HELISA", "Programación", "Obligatorio · programacion.xls",
            "Informe de cuentas por pagar de HELISA. Se toman los documentos "
            "con <b>saldo actual</b> mayor a cero: cuenta, NIT, proveedor, "
            "tipo, número, fechas, valor y saldo. El abono es valor − saldo.")
        f_prog = st.file_uploader("Programación HELISA",
                                  type=["xls", "xlsx", "xml"],
                                  key="pp_programacion",
                                  label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "HELISA", "Conceptos", "Obligatorio · conceptos.xls",
            "Informe de conceptos de HELISA. Da el <b>texto capturado</b> de "
            "cada documento, que se usa como concepto de las facturas "
            "nuevas (las que ya estaban en la programación anterior "
            "conservan el texto que se les dio allí).")
        f_conc = st.file_uploader("Conceptos HELISA",
                                  type=["xls", "xlsx", "xml"],
                                  key="pp_conceptos",
                                  label_visibility="collapsed")
    with c3:
        encabezado_carga(
            "ANT", "Programación anterior", "Obligatorio · PROG. PAGOS …",
            "La programación de pagos más reciente de la empresa. Solo se "
            "lee. Sus hojas auxiliares (proyección de cobros, cosecha, "
            "contratistas…) se copian tal cual en el libro nuevo.")
        f_ant = st.file_uploader("Programación anterior",
                                 type=["xls", "xlsx"], key="pp_anterior",
                                 label_visibility="collapsed")
    if not (f_prog and f_conc and f_ant):
        st.info("Carga los tres archivos para continuar.")
        return

    try:
        with st.spinner("Leyendo los archivos…"):
            helisa, conceptos, anterior = _leer_entradas_pp(
                f_prog.getvalue(), f_conc.getvalue(), f_ant.getvalue(),
                f_ant.name)
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    if anterior.get("empresa") and empresa_implementada(
            anterior["empresa"]) not in (None, clave):
        st.warning(f"La programación anterior parece ser de "
                   f"«{anterior['empresa']}», no de {nombre_empresa}.")
    con_saldo = sum(1 for d in helisa["documentos"] if d["saldo"] > 0.004)
    st.success(
        f"HELISA: {len(helisa['documentos'])} documentos, {con_saldo} con "
        f"saldo ({formato_cop(helisa['total_saldo'])}) · Conceptos: "
        f"{len(conceptos)} documentos · Anterior: hoja «{anterior['hoja']}» "
        f"del {anterior['fecha']:%d/%m/%Y} con "
        f"{len(anterior['facturas'])} facturas, "
        f"{len(anterior['anticipos'])} anticipos y "
        f"{sum(len(g['items']) for g in anterior['fijos'])} pagos fijos."
        if anterior.get("fecha") else "Archivos leídos.")
    if anterior["libro"]["fuente"] != "completo" and \
            anterior["hojas_auxiliares"]:
        st.caption("La programación anterior es .xls y en este equipo no hay "
                   "Excel ni LibreOffice para convertirla: las hojas "
                   "auxiliares se copian con sus valores y formato básico "
                   "(sin fórmulas).")

    titulo_seccion(
        "Fechas y saldos", 3,
        "La <b>fecha de la programación</b> va en el título y en el nombre "
        "del archivo. Las <b>fechas de pago</b> son las columnas «Pagos "
        "al…» (por defecto los viernes que quedan del mes). Lo programado "
        "en la anterior para una fecha que ya pasó se da por pagado; lo "
        "programado a futuro se corre a la nueva columna de esa fecha.")
    c1, c2 = st.columns([1, 2])
    with c1:
        fecha = st.date_input("Fecha de la programación",
                              value=datetime.date.today(), key="pp_fecha",
                              format="DD/MM/YYYY")
    sugeridas = fechas_pago_sugeridas(fecha, empresa.get("dia_pago", 4))
    posibles = [sugeridas[0] + datetime.timedelta(days=7 * k)
                for k in range(-1, 8)]
    posibles = [f for f in posibles if f >= fecha - datetime.timedelta(7)]
    with c2:
        fechas_pago = st.multiselect(
            "Fechas de pago (columnas)", posibles, default=sugeridas,
            key=f"pp_fechas_{fecha}",
            format_func=lambda f: f"{DIAS_PP[f.weekday()]} {f:%d/%m/%Y}")
    fechas_pago = sorted(fechas_pago)
    if not fechas_pago:
        st.warning("Escoge al menos una fecha de pago.")
        return
    disponible, ingresos = [], []
    columnas = st.columns(len(fechas_pago) + 1)
    with columnas[0]:
        trm = st.number_input("TRM", min_value=0.0, step=1.0, format="%.2f",
                              value=float(anterior.get("trm") or 0),
                              key="pp_trm")
    for i, f in enumerate(fechas_pago):
        with columnas[i + 1]:
            disponible.append(st.number_input(
                f"Disponible en bancos · {f:%d/%m}", min_value=None,
                step=1000.0, format="%.2f", value=0.0,
                key=f"pp_disp_{f}",
                help="Saldo disponible para esa fecha (fila TOTAL "
                     "DISPONIBLE)."))
            ingresos.append(st.number_input(
                f"Ingresos esperados · {f:%d/%m}", step=1000.0,
                format="%.2f", value=0.0, key=f"pp_ing_{f}",
                help="Cobros que se esperan recibir (fila 2 de la "
                     "programación; en rojo)."))

    # --- Partidas sugeridas y revision ---------------------------------
    huella = _huella(f_prog.getvalue(), f_conc.getvalue(), f_ant.getvalue(),
                     fecha, fechas_pago, clave)
    if st.session_state.get("pp_huella") != huella:
        st.session_state["pp_huella"] = huella
        st.session_state["pp_partidas"] = armar_prog_pagos(
            helisa, conceptos, anterior, fecha, fechas_pago, empresa)
        st.session_state["pp_editor_n"] = \
            st.session_state.get("pp_editor_n", 0) + 1
        st.session_state.pop("pp_archivo", None)
    partidas = st.session_state["pp_partidas"]

    titulo_seccion(
        "Revisión", 4,
        "Cada fila es una partida de la nueva programación con lo que "
        "sugiere la plataforma: si se <b>incluye</b> y en qué <b>fecha de "
        "pago</b>. Puedes cambiar ambas, el concepto y las observaciones; "
        "las columnas grises son de solo lectura. La columna <b>Motivo</b> "
        "explica la sugerencia. Activa «Mostrar también las que salen» para "
        "ver lo que se da por pagado y volverlo a incluir si hace falta. "
        "Pasa el cursor por cada <b>?</b> de los campos para ver qué "
        "significa en términos contables.")
    _glosario_pp(GLOSARIO_NATURE)
    st.caption("Reglas usadas: lo programado en la anterior para una fecha "
               "que ya pasó se da por pagado · lo programado a futuro pasa "
               "a la columna de esa fecha · facturas nuevas con saldo en "
               "HELISA → primera fecha de pago · pagos fijos pagados o con "
               "fecha vencida → mes siguiente · pagos parciales → fila "
               "«SALDO, …».")
    ayudas = dict(GLOSARIO_NATURE)
    sin_html = lambda t: re.sub(r"<[^>]+>", "", t)
    mostrar_todas = st.toggle("Mostrar también las que salen",
                              key="pp_mostrar_todas")
    tabla, opciones = _tabla_revision_pp(partidas, fechas_pago,
                                         mostrar_todas)
    if tabla is not None:
        editada = st.data_editor(
            tabla, key=f"pp_editor_{st.session_state['pp_editor_n']}_"
                       f"{_huella(*tabla.index)[:10]}",
            use_container_width=True, height=520,
            column_config={
                "Incluir": st.column_config.CheckboxColumn(
                    width="small", help=sin_html(ayudas["Incluir"])),
                "Sección": st.column_config.TextColumn(
                    disabled=True, width="small",
                    help=sin_html(ayudas["Sección"])),
                "Proveedor / grupo": st.column_config.TextColumn(
                    disabled=True),
                "Número": st.column_config.TextColumn(
                    disabled=True, width="small",
                    help=sin_html(ayudas["Número"])),
                "Concepto": st.column_config.TextColumn(
                    width="large", help=sin_html(ayudas["Concepto"])),
                "Saldo": st.column_config.NumberColumn(
                    disabled=True, format="%.2f",
                    help=sin_html(ayudas["Saldo"])),
                "Programar": st.column_config.SelectboxColumn(
                    options=opciones, required=True,
                    help=sin_html(ayudas["Programar"])),
                "Observaciones": st.column_config.TextColumn(
                    help=sin_html(ayudas["Observaciones"])),
                "Origen": st.column_config.TextColumn(
                    disabled=True, help=sin_html(ayudas["Origen"])),
                "Motivo": st.column_config.TextColumn(
                    disabled=True, width="large",
                    help=sin_html(ayudas["Motivo"])),
            })
        _aplicar_revision_pp(partidas, editada, opciones)

    # v6.7: lo que se da por pagado SOLO porque estaba programado en una
    # fecha que ya paso (sin verlo en HELISA ni en el banco) se avisa.
    # Las facturas no: si HELISA ya no las muestra con saldo, HELISA lo
    # confirma. Anticipos y pagos fijos no tienen ese respaldo.
    supuestos = [p for p in partidas if p.get("seccion") != "factura"
                 and ((not p["incluir"]
                       and "ya pasó" in str(p.get("motivo") or ""))
                      or "pasa al mes siguiente" in str(p.get("motivo")
                                                        or ""))]
    if supuestos:
        uno = len(supuestos) == 1
        st.warning(
            f"**Revisar: {len(supuestos)} anticipo"
            f"{'' if uno else 's'} o pago{'' if uno else 's'} fijo"
            f"{'' if uno else 's'} se {'da' if uno else 'dan'} por "
            f"pagado{'' if uno else 's'} solo porque estaba"
            f"{'' if uno else 'n'} programado{'' if uno else 's'} en una "
            "fecha que ya pasó** (no se confirmó contra el banco ni HELISA). "
            "Si alguno no se pagó, corrígelo en la tabla (activa «Mostrar "
            "también las que salen»):\n\n"
            + "\n".join(f"- {p.get('proveedor') or p.get('grupo') or ''} "
                         f"{p.get('numero') or ''} {p.get('concepto') or ''}"
                         f" · {formato_cop(p.get('saldo') or 0)}"
                         for p in supuestos[:12])
            + (f"\n- … y {len(supuestos) - 12} más." if len(supuestos) > 12
               else ""))
    resumen = resumen_prog_pagos(partidas, fechas_pago)
    columnas = st.columns(len(fechas_pago) + 2)
    columnas[0].metric("Partidas incluidas", resumen["incluidas"],
                       f"{resumen['excluidas']} salen", delta_color="off")
    for i, f in enumerate(fechas_pago):
        diferencia = disponible[i] + ingresos[i] - resumen["por_fecha"][i]
        columnas[i + 1].metric(f"A pagar el {f:%d/%m}",
                               formato_cop(resumen["por_fecha"][i]),
                               f"Diferencia {formato_cop(diferencia)}",
                               delta_color="normal" if diferencia >= 0
                               else "inverse")
    columnas[-1].metric("Pendiente total", formato_cop(resumen["pendiente"]),
                        f"Sin programar {formato_cop(resumen['sin_fecha'])}",
                        delta_color="off")

    _visor_revision_pp(
        partidas, orden_partidas,
        f"Programación anterior · {anterior.get('archivo', '')} · hoja "
        f"{anterior['hoja']}",
        anterior["libro"]["hojas"][anterior["hoja"]],
        f"HELISA programación · {f_prog.name}", helisa["tabla"], "pp")

    titulo_seccion(
        "Generar y descargar", 6,
        "Genera el libro <b>PROG PAGOS</b> con la fecha y el nombre de la "
        "empresa. La hoja principal se arma con un formato uniforme y "
        "fórmulas (abonos, saldos a pagar, subtotales, gran total, "
        "diferencia y TRM). El archivo se descarga: guárdalo tú en la "
        "carpeta que corresponda.")
    if st.button("Generar PROG PAGOS ACTUAL", type="primary",
                 key="pp_generar", use_container_width=True):
        try:
            with st.spinner("Armando el libro…"):
                contenido = generar_excel_prog_pagos(partidas, {
                    "empresa": empresa, "nombre_empresa": nombre_empresa,
                    "fecha": fecha, "fechas_pago": fechas_pago,
                    "disponible": disponible, "ingresos": ingresos,
                    "trm": trm, "anterior": anterior,
                    "titulo_gastos": anterior.get("titulo_gastos")})
            st.session_state["pp_archivo"] = (
                nombre_archivo_prog(nombre_empresa, fecha), contenido)
        except Exception as error:
            reportar_error("No se pudo generar el archivo", error)
    if st.session_state.get("pp_archivo"):
        nombre, contenido = st.session_state["pp_archivo"]
        st.success(f"Listo: {nombre}")
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary", key="pp_descargar", use_container_width=True)


@_cache_datos
def _leer_entradas_cxp(hel_bytes, ant_bytes, ant_nombre):
    return leer_cxp_helisa(hel_bytes), leer_cxp_anterior(ant_bytes,
                                                          ant_nombre)


def _tabla_revision_cxp(partidas, fecha, mostrar_todas):
    import pandas as pd
    filas = []
    for p in orden_cxp(partidas):
        if not mostrar_todas and not p["incluir"]:
            continue
        dias = (fecha - p["vence"]).days if p.get("vence") else 0
        filas.append({
            "id": p["id"], "Incluir": bool(p["incluir"]),
            "Proveedor": p["proveedor"], "Documento": p["numero"],
            "Vence": p["vence"].strftime("%d/%m/%Y") if p.get("vence")
            else (p.get("vence_texto") or ""), "Días": max(dias, 0),
            "Saldo HELISA": float(p["valor"]),
            "Lo que se paga": float(p.get("pagar") or 0),
            "Observaciones": p.get("obs") or "",
            "Origen": p.get("origen") or "", "Motivo": p.get("motivo") or "",
        })
    return pd.DataFrame(filas).set_index("id") if filas else None


def _aplicar_revision_cxp(partidas, editada):
    por_id = {p["id"]: p for p in partidas}
    for ident, fila in editada.iterrows():
        p = por_id.get(ident)
        if p is None:
            continue
        p["incluir"] = bool(fila["Incluir"])
        p["obs"] = str(fila["Observaciones"] or "")
        try:
            p["pagar"] = round(float(fila["Lo que se paga"]), 2)
        except (TypeError, ValueError):
            p["pagar"] = p["valor"]


def _editor_filas_extra(filas, columnas, llave, ayuda):
    """Editor de filas que no salen de HELISA (se pueden cambiar valores,
    agregar o quitar filas). Devuelve la lista de dicts editada."""
    import pandas as pd
    datos = pd.DataFrame(
        [{c: (f.get(k, True) if k == "incluir" else f.get(k))
          for c, k in columnas} for f in filas]
        or [{c: None for c, _ in columnas}])
    editada = st.data_editor(
        datos, key=llave, num_rows="dynamic", use_container_width=True,
        hide_index=True, column_config={
            "Incluir": st.column_config.CheckboxColumn(width="small",
                                                       help=ayuda or None),
            "Valor": st.column_config.NumberColumn(format="%.2f"),
            "Observaciones": st.column_config.TextColumn(width="large"),
        })
    salida = []
    for _, fila in editada.iterrows():
        item = {k: fila[c] for c, k in columnas}
        try:
            item["valor"] = round(float(item.get("valor") or 0), 2)
        except (TypeError, ValueError):
            item["valor"] = 0.0
        texto = " ".join(str(v) for k, v in item.items()
                         if k not in ("valor", "incluir") and v
                         and str(v) != "nan").strip()
        if not texto and not item["valor"]:
            continue
        for k, v in list(item.items()):
            if k not in ("valor", "incluir") and (v is None or
                                                   str(v) == "nan"):
                item[k] = ""
        marca = item.get("incluir")
        item["incluir"] = True if marca is None or str(marca) in (
            "nan", "None") else bool(marca)
        salida.append(item)
    return salida


def _secciones_extra_cxp(partidas, anterior, opciones, huella, cobrar):
    """v6.10 (CAFETO): secciones de la lista anterior que no salen de
    HELISA (SEGURIDAD SOCIAL, IMPUESTOS, PAGOS FIJOS) y anticipos
    pendientes por legalizar. Se muestran para revisarlas y se copian al
    archivo tal como queden; la plataforma no inventa valores. Devuelve
    (manuales, anticipos)."""
    manuales = anterior.get("manuales") or []
    anticipos = anterior.get("anticipos") or []
    if not (manuales or anticipos):
        return [], []
    for m in manuales + anticipos:
        if isinstance(m.get("fecha"), datetime.date):
            m.setdefault("fecha_txt", m["fecha"].strftime("%d/%m/%Y"))
        else:
            m.setdefault("fecha_txt", m.get("fecha_texto") or "")
    salida_m, salida_a = [], []
    if manuales:
        titulo_seccion(
            "Secciones que no salen de HELISA", None,
            "Filas que la lista anterior lleva a mano (seguridad social por "
            "mes, retención en la fuente, libranzas y otros pagos fijos). "
            "<b>Se copian tal como estaban</b>: actualiza aquí los valores, "
            "agrega el mes nuevo o quita lo que ya se pagó antes de "
            "generar. La plataforma no calcula ni inventa estos valores.")
        st.warning("Estas filas vienen de la lista anterior sin cambios: "
                   "confírmalas antes de generar.")
        salida_m = _editor_filas_extra(
            manuales, [("Incluir", "incluir"), ("Sección", "seccion"),
                       ("Descripción", "descripcion"), ("Fecha", "fecha_txt"),
                       ("Valor", "valor"), ("Observaciones", "obs")],
            f"cxp_manuales_{huella[:10]}",
            "Desmarca para no llevar la fila al archivo.")
        if opciones.get("terceros_fuera"):
            filas_ss, personas = comparar_seguridad_social(
                partidas, salida_m, opciones["terceros_fuera"][0])
            if filas_ss:
                import pandas as pd
                tabla = pd.DataFrame([{
                    "Mes": mes, "HELISA (entidades de seguridad social)": h,
                    "En la lista": m, "Diferencia": round(m - h, 2)}
                    for mes, h, m in filas_ss])
                distintas = [f for f in filas_ss if abs(f[1] - f[2]) > 0.005]
                with st.expander(
                        "Seguridad social: lista vs. HELISA por mes"
                        + (f" · {len(distintas)} mes(es) no coinciden"
                           if distintas else " · coincide"),
                        expanded=bool(distintas)):
                    st.caption("Referencia: suma de los documentos "
                               "pendientes en HELISA de EPS, fondos de "
                               "pensiones, cajas de compensación, ARL, ICBF "
                               "y SENA, por mes de emisión. No cambia la "
                               "lista: sirve para revisar los valores "
                               "digitados.")
                    st.dataframe(tabla, use_container_width=True,
                                 hide_index=True)
            if personas:
                st.info("Documentos de nómina pendientes en HELISA a "
                        "personas (no entidades), que no están en el listado "
                        "ni en una sección: "
                        + "; ".join(f"{p['proveedor']} {p['numero']} "
                                    f"({formato_cop(p['valor'])})"
                                    for p in personas[:8])
                        + ". Inclúyelos en el listado o en PAGOS FIJOS si "
                        "corresponde.")
    if anticipos:
        titulo_seccion(
            "Anticipos pendientes por legalizar", None,
            "Bloque de la lista anterior que va después del total. Se copia "
            "tal cual; revisa y actualiza aquí.")
        salida_a = _editor_filas_extra(
            anticipos, [("Incluir", "incluir"), ("Título", "titulo"),
                        ("Tercero", "tercero"), ("Documento", "numero"),
                        ("Fecha", "fecha_txt"), ("Valor", "valor"),
                        ("Observaciones", "obs")],
            f"cxp_anticipos_{huella[:10]}",
            "Desmarca para no llevar el anticipo al archivo.")
    for item in salida_m + salida_a:
        item["fecha_texto"] = item.pop("fecha_txt", "") or ""
        item["fecha"] = None
    return salida_m, salida_a


def _flujo_cxp(clave, empresa):
    """Programacion tipo cuentas por pagar con observaciones (MEDFAM,
    CAFETO). v6.10: empresas con variantes (CAFETO: por pagar / por
    cobrar) muestran primero el selector."""
    variante, opciones = "pagar", {}
    if empresa.get("variantes"):
        variantes = empresa["variantes"]
        variante = st.radio(
            "¿Qué listado vas a actualizar?", list(variantes),
            format_func=lambda k: variantes[k]["etiqueta"], horizontal=True,
            key=f"cxp_variante_{clave}",
            help="Cuentas por pagar: listado de facturas por pagar de "
                 "acreedores de HELISA. Cuentas por cobrar: planilla para "
                 "cobros de clientes (cartera) de HELISA. Las dos conservan "
                 "las observaciones de la lista anterior.")
        opciones = variantes[variante]
    cobrar = variante == "cobrar"
    quien = "cliente" if cobrar else "proveedor"
    listado = ("Planilla para cobros de clientes" if cobrar else
               "Lista de facturas por pagar de acreedores")
    titulo_seccion(
        "Archivos", 2,
        f"Los dos son <b>obligatorios</b>. El listado de <b>cuentas por "
        f"{'cobrar' if cobrar else 'pagar'}</b> se carga <b>tal como se "
        f"descarga de HELISA</b> ({listado}). La <b>lista anterior</b> es "
        "el último archivo que se entregó: de él se toman las "
        "observaciones" + ("" if cobrar else " y, si las tiene, las "
                            "secciones que no salen de HELISA (seguridad "
                            "social, impuestos, pagos fijos, anticipos)")
        + ".")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga(
            "HELISA", f"Cuentas por {'cobrar' if cobrar else 'pagar'}",
            "Obligatorio · listado .xls de HELISA",
            f"{listado} de HELISA, agrupado por {quien}: documento, fecha "
            "de emisión, vencimiento y saldo. Es la base de la nueva lista: "
            "todo lo pendiente en HELISA entra.")
        f_hel = st.file_uploader("Listado HELISA",
                                 type=["xls", "xlsx", "xml"],
                                 key=f"cxp_helisa_{variante}",
                                 label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "ANT", "Programación anterior", "Obligatorio · la última "
            "entregada (.xls o .xlsx)",
            "La programación anterior con su columna OBSERVACIONES. Solo se "
            "lee: las observaciones pasan a los mismos documentos (también "
            "las que cubren varias facturas a la vez).")
        f_ant = st.file_uploader("Programación anterior",
                                 type=["xls", "xlsx"],
                                 key=f"cxp_anterior_{variante}",
                                 label_visibility="collapsed")
    if not (f_hel and f_ant):
        st.info("Carga los dos archivos para continuar.")
        return
    try:
        with st.spinner("Leyendo los archivos…"):
            helisa, anterior = _leer_entradas_cxp(
                f_hel.getvalue(), f_ant.getvalue(), f_ant.name)
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    if helisa.get("empresa") and empresa_implementada(
            helisa["empresa"]) not in (None, clave):
        st.warning(f"El listado de HELISA parece ser de "
                   f"«{helisa['empresa']}», no de {empresa['nombre']}.")
    if helisa.get("clase") and helisa["clase"] != variante:
        st.warning("El listado de HELISA parece de cuentas por "
                   f"{helisa['clase']} y elegiste cuentas por {variante}. "
                   "Se usa tal como se cargó; revisa que sea el correcto.")
    truncadas = [d for d in helisa["documentos"]
                 if not d["fecha"] and d.get("fecha_texto")]
    if truncadas:
        st.warning(
            f"{len(truncadas)} documento(s) de HELISA traen la fecha con el "
            "año cortado (p. ej. «" + truncadas[0]["fecha_texto"] + "»). "
            "Se incluyen con la fecha tal como viene, sin calcular "
            "vencimiento; confírmalas en HELISA: "
            + ", ".join(f"{d['numero']} ({formato_cop(d['valor'])})"
                        for d in truncadas[:6])
            + ("…" if len(truncadas) > 6 else "") + ".")
    st.success(
        f"HELISA: {len(helisa['documentos'])} documentos de "
        f"{len(groupby_proveedor(helisa['documentos']))} proveedores "
        f"({formato_cop(helisa['total'])})"
        + (f", elaborado el {helisa['fecha_informe']:%d/%m/%Y}"
           if helisa.get("fecha_informe") else "")
        + f" · Anterior: {len(anterior['documentos'])} documentos"
        + (f" al {anterior['fecha']:%d/%m/%Y}" if anterior.get("fecha")
           else "")
        + f", {sum(1 for d in anterior['documentos'] if d['obs'])} con "
          "observación.")

    titulo_seccion(
        "Fecha y opciones", 3,
        "La <b>fecha de la programación</b> va en el título («Lista de "
        "facturas por pagar de acreedores a …»), en el nombre de la hoja y "
        "del archivo, y es la fecha contra la que se calculan los días de "
        "vencimiento.")
    c1, c2 = st.columns([1, 2])
    with c1:
        fecha = st.date_input(
            "Fecha de la programación",
            value=helisa.get("fecha_informe") or datetime.date.today(),
            key="cxp_fecha", format="DD/MM/YYYY")
    with c2:
        st.write("")
        textos_venc = " / ".join(f"«{t}»" for t in dict.fromkeys(
            (opciones.get("vencidas") or {"FCC": "FACTURA VENCIDA",
                                          "DSEC": "CUENTA DE COBRO VENCIDA"}
             ).values()))
        marcar = st.checkbox(
            f"Escribir {textos_venc} en los documentos vencidos sin "
            "observación", value=opciones.get("marcar_vencidas", True),
            key=f"cxp_marcar_{variante}",
            help="Todo documento cuyo vencimiento es anterior a la fecha de "
                 "la programación y no tiene otra observación queda marcado "
                 "como vencido, también los que venían de la programación "
                 "anterior y en ese momento aún no vencían. Las "
                 "observaciones que ya tenga un documento se respetan. FCC → "
                 "FACTURA VENCIDA; DSEC → CUENTA DE COBRO VENCIDA.")

    huella = _huella(f_hel.getvalue(), f_ant.getvalue(), fecha, marcar, clave,
                     variante)
    if st.session_state.get("pp_huella") != huella:
        st.session_state["pp_huella"] = huella
        st.session_state["pp_partidas"] = armar_cxp_medfam(
            helisa, anterior, fecha, marcar, opciones)
        st.session_state["pp_editor_n"] = \
            st.session_state.get("pp_editor_n", 0) + 1
        st.session_state.pop("pp_archivo", None)
    partidas = st.session_state["pp_partidas"]

    titulo_seccion(
        "Revisión", 4,
        "Cada fila es un documento del listado de HELISA con lo que sugiere "
        "la plataforma: si se <b>incluye</b>, <b>lo que se paga</b> y la "
        "<b>observación</b> (traída de la anterior). Las columnas grises son "
        "de solo lectura. Activa «Mostrar también las que salen» para ver "
        "los documentos que se dejan por fuera (saldo cero, centavos o ya "
        "pagados). Pasa el cursor por cada <b>?</b> para ver qué significa "
        "cada campo en términos contables.")
    _glosario_pp(GLOSARIO_CXP)
    st.caption("Reglas usadas: entra todo lo pendiente en el listado de "
               "HELISA · las observaciones pasan del mismo documento de la "
               "anterior · factura y nota del mismo valor se anulan · saldos "
               "de centavos no se programan · lo que estaba antes y ya no "
               "está en HELISA se da por pagado.")
    ayudas = {k: re.sub(r"<[^>]+>", "", v) for k, v in GLOSARIO_CXP}
    mostrar_todas = st.toggle("Mostrar también las que salen",
                              key="cxp_mostrar_todas")
    tabla = _tabla_revision_cxp(partidas, fecha, mostrar_todas)
    if tabla is not None:
        editada = st.data_editor(
            tabla, key=f"cxp_editor_{st.session_state['pp_editor_n']}_"
                       f"{_huella(*tabla.index)[:10]}",
            use_container_width=True, height=520,
            column_config={
                "Incluir": st.column_config.CheckboxColumn(
                    width="small", help=ayudas["Incluir"]),
                "Proveedor": st.column_config.TextColumn(disabled=True),
                "Documento": st.column_config.TextColumn(
                    disabled=True, help=ayudas["Documento"]),
                "Vence": st.column_config.TextColumn(
                    disabled=True, width="small",
                    help=ayudas["Vence / Días"]),
                "Días": st.column_config.NumberColumn(
                    disabled=True, width="small",
                    help=ayudas["Vence / Días"]),
                "Saldo HELISA": st.column_config.NumberColumn(
                    disabled=True, format="%.2f",
                    help=ayudas["Saldo HELISA"]),
                "Lo que se paga": st.column_config.NumberColumn(
                    format="%.2f", help=ayudas["Lo que se paga"]),
                "Observaciones": st.column_config.TextColumn(
                    width="large", help=ayudas["Observaciones"]),
                "Origen": st.column_config.TextColumn(
                    disabled=True, help=ayudas["Origen"]),
                "Motivo": st.column_config.TextColumn(
                    disabled=True, width="large", help=ayudas["Motivo"]),
            })
        _aplicar_revision_cxp(partidas, editada)

    excluidos = [p["aviso_exclusion"] for p in partidas
                 if p.get("aviso_exclusion") and not p["incluir"]]
    if excluidos:
        st.warning("**Revisar (no se programan, no se asume nada):**\n\n"
                   + "\n".join(f"- {t}" for t in excluidos[:15])
                   + (f"\n- … y {len(excluidos) - 15} más (ver «Mostrar "
                      "también las que salen»)." if len(excluidos) > 15
                      else ""))
    resumen = resumen_cxp(partidas, fecha)
    c = st.columns(4)
    c[0].metric("Documentos incluidos", resumen["incluidas"],
                f"{resumen['excluidas']} salen", delta_color="off")
    c[1].metric("Clientes" if cobrar else "Proveedores",
                resumen["proveedores"])
    c[2].metric("Total a cobrar" if cobrar else "Total a pagar",
                formato_cop(resumen["total"]))
    c[3].metric("De eso, vencido", formato_cop(resumen["vencido"]))

    manuales, anticipos = _secciones_extra_cxp(
        partidas, anterior, opciones, huella, cobrar)

    _visor_revision_pp(
        partidas, orden_cxp,
        f"Programación anterior · {anterior.get('archivo', '')}",
        anterior["tabla"],
        f"HELISA cuentas por {'cobrar' if cobrar else 'pagar'} · "
        f"{f_hel.name}", helisa["tabla"], "cxp")

    prefijo = opciones.get("prefijo") or "CUENTAS X PAGAR"
    titulo_seccion(
        "Generar y descargar", 6,
        f"Genera el libro <b>{prefijo} AL {{fecha}}</b> con el mismo "
        f"formato de la empresa: {quien}, documento, fechas, valor y "
        f"observaciones (en rojo), total por {quien}"
        + (", las secciones que no salen de HELISA y los anticipos"
           if manuales or anticipos else "")
        + " y el total general. El archivo se descarga: guárdalo tú en la "
        "carpeta que corresponda.")
    if st.button("Generar programación actual", type="primary",
                 key="cxp_generar", use_container_width=True):
        try:
            with st.spinner("Armando el libro…"):
                ctx = {"fecha": fecha,
                       "nombre_empresa": helisa.get("empresa") or
                       empresa["nombre"],
                       "nit_texto": helisa.get("nit_texto"),
                       "anterior": anterior, "modo": variante,
                       "manuales": manuales, "anticipos": anticipos}
                if opciones.get("hoja"):
                    ctx["hoja"] = opciones["hoja"].format(fecha=fecha)
                if opciones.get("total"):
                    ctx["total_label"] = opciones["total"].format(
                        fecha=fecha)
                contenido = generar_excel_cxp(partidas, ctx)
            st.session_state["pp_archivo"] = (
                nombre_archivo_cxp(helisa.get("empresa") or
                                   empresa["nombre"], fecha, prefijo),
                contenido)
        except Exception as error:
            reportar_error("No se pudo generar el archivo", error)
    if st.session_state.get("pp_archivo"):
        nombre, contenido = st.session_state["pp_archivo"]
        st.success(f"Listo: {nombre}")
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary", key="cxp_descargar", use_container_width=True)
