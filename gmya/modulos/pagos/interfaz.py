"""Pantalla "Programacion de pagos" (Streamlit). Contrato: modulo_prog_pagos().

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.cache, gmya.comun.config_equipo, gmya.ui.componentes, gmya.ui.visor, gmya.modulos.pagos.lectura, gmya.modulos.pagos.reglas, gmya.modulos.pagos.excel, gmya.modulos.pagos.empresa_d, gmya.ui.interfaz_comun, gmya.registro.interfaz
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
from gmya.modulos.pagos.empresa_d import (
    armar_cxp_empresa_d, comparar_seguridad_social, generar_excel_cxp,
    groupby_proveedor, leer_cxp_anterior, leer_cxp_helisa,
    nombre_archivo_cxp, orden_cxp, resumen_cxp,
)
from gmya.modulos.pagos.empresa_e import (
    armar_empresa_e, generar_excel_empresa_e, leer_empresa_e_anterior, nombre_archivo_empresa_e,
    resumen_empresa_e,
)
from gmya.ui.interfaz_comun import _filtro_visor, _mostrar_visor
import gmya.modulos.pagos.empresa_b as EMPRESA_B
from gmya.ui.diferencias import mostrar_diferencias
from gmya.modulos.pagos.diferencias import datos_graficos, panel_revision_pagos
from gmya.ui.visual import (
    grafico, html_antiguedad, html_barras_valor, html_comparativo, kpis,
    pesos,
)
from gmya.registro.interfaz import reportar_error


# ============================================================
# INTERFAZ: PROGRAMACION DE PAGOS
# ============================================================
# v6.12: los estilos del selector de empresas y del glosario pasaron a
# gmya/ui/estilos.py (sistema de diseno comun).
CSS_PROG_PAGOS = ""

DIAS_PP = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

TIP_NO_IMPLEMENTADA = (
    "<b>Aún no implementado.</b> La programación de pagos de esta empresa "
    "todavía no está configurada en la plataforma. Cuando se configure "
    "(con su programación anterior y sus informes de HELISA de ejemplo) "
    "quedará disponible aquí.")


def _ficha_no_implementada(nombre):
    st.markdown(
        f'<div class="gm-emp-off" tabindex="0">'
        f'<span class="gm-emp-nombre">{html.escape(nombre)}</span>'
        f'<span class="gm-emp-candado">Próximamente</span>'
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
    if CSS_PROG_PAGOS:
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
    # v6.14: panel de revision (composicion + partidas por confirmar) como
    # vista principal; el visor queda como opcion.
    titulo_seccion(
        "Revisión de la programación", 5,
        "Cómo se compone el total incluido: lo que pasa <b>sin novedad</b> y "
        "las partidas que conviene <b>confirmar</b> antes de enviar (si "
        "siguen vigentes, si el valor es correcto, si ya se pagaron). Abre "
        "una partida para ver el detalle; si no corresponde, desmárcala en "
        "la tabla de revisión (columna Incluir).")
    mostrar_diferencias(
        panel_revision_pagos(partidas, ordenar, "Programación actual"),
        f"{clave}_rev", visor=lambda: _visor_documentos_pp(
            partidas, ordenar, ant_titulo, tabla_ant, hel_titulo, tabla_hel,
            clave, explicacion_extra))


def _visor_documentos_pp(partidas, ordenar, ant_titulo, tabla_ant,
                         hel_titulo, tabla_hel, clave, explicacion_extra=""):
    st.markdown('<div class="gm-pa-pie">' + (
        "Muestra la <b>programación anterior</b> y el informe de "
        "<b>HELISA</b> completos, cada uno con su desplazamiento y el número "
        "de fila del archivo. Se marcan (número y color) solo las partidas "
        "que <b>se están incluyendo</b> pero conviene confirmar: si siguen "
        "vigentes, si el valor es correcto o si se deben seguir pasando. "
        "Pasa el mouse sobre una fila marcada para ver qué revisar. "
        "<b>Siguiente ▶</b> salta a la próxima marca en ese documento; "
        "<b>Ctrl + rueda</b> hace zoom." + explicacion_extra) + "</div>",
                unsafe_allow_html=True)
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


def _graficos_programacion(partidas, fecha, clave, quien="Proveedor",
                           comparativo=None):
    """v6.16: antiguedad de lo incluido, concentracion por tercero y (si
    se pasa) lo que se paga en cada fecha frente al dinero disponible."""
    g = datos_graficos(partidas, fecha)
    vistas = ["Antigüedad", f"{quien}es" if not quien.endswith("e")
              else f"{quien}s"]
    if comparativo:
        vistas.append("Flujo por fecha")
    ver = st.radio("Ver", vistas, horizontal=True, key=f"{clave}_graf_ver",
                   label_visibility="collapsed")
    if ver == "Antigüedad":
        grafico(f"Antigüedad al {fecha:%d/%m/%Y}", html_antiguedad(
            g["antiguedad"], "días desde el vencimiento"),
            nota="Solo partidas incluidas", icono_nombre="reloj")
    elif ver == "Flujo por fecha":
        grafico("Por fecha de pago: a pagar vs disponible + ingresos",
                html_comparativo(comparativo, "A pagar", "Disponible + "
                                 "ingresos", color_a="#E0118F",
                                 color_b="#5FD3CB", texto_diferencia=lambda d:
                                 "Alcanza justo" if abs(d) < .005 else
                                 (f"Falta {pesos(d)}" if d > 0 else
                                  f"Sobra {pesos(-d)}"),
                                 ok_si=lambda d: d <= 0.005),
                icono_nombre="calendario")
    else:
        k, n = g["concentracion"]
        grafico(f"{vistas[1]} con mayor valor", html_barras_valor(
            g["terceros"]), nota=f"{k} de {n} suman el 80 % del total",
            icono_nombre="personas")


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


GLOSARIO_EMPRESA_C = [
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
    if empresa.get("formato") == "empresa_b":
        _flujo_empresa_b(clave, empresa)
    elif empresa.get("formato") == "empresa_e":
        _flujo_empresa_e(clave, empresa)
    elif empresa.get("formato") == "cxp":
        _flujo_cxp(clave, empresa)
    else:
        _flujo_flujo_caja(clave, empresa)


def _flujo_flujo_caja(clave, empresa):
    """Programacion con flujo de caja (EMPRESA C)."""
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
    _glosario_pp(GLOSARIO_EMPRESA_C)
    st.caption("Reglas usadas: lo programado en la anterior para una fecha "
               "que ya pasó se da por pagado · lo programado a futuro pasa "
               "a la columna de esa fecha · facturas nuevas con saldo en "
               "HELISA → primera fecha de pago · pagos fijos pagados o con "
               "fecha vencida → mes siguiente · pagos parciales → fila "
               "«SALDO, …».")
    ayudas = dict(GLOSARIO_EMPRESA_C)
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

    _graficos_programacion(partidas, fecha, "pp", "Proveedor", [
        (f"Pagos al {f:%d/%m/%Y}", resumen["por_fecha"][i],
         round(disponible[i] + ingresos[i], 2))
        for i, f in enumerate(fechas_pago)])
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
    """v6.10 (EMPRESA F): secciones de la lista anterior que no salen de
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


@_cache_datos
def _leer_entradas_empresa_e(hel_bytes, ant_bytes, ant_nombre, modo):
    return (leer_cxp_helisa(hel_bytes),
            leer_empresa_e_anterior(ant_bytes, ant_nombre, modo))


def _flujo_empresa_e(clave, empresa):
    """v6.11: programacion de EMPRESA E SAS (por pagar y por
    cobrar) con su formato propio."""
    import pandas as pd
    variantes = empresa["variantes"]
    modo = st.radio("¿Qué listado vas a actualizar?", list(variantes),
                    format_func=lambda k: variantes[k]["etiqueta"],
                    horizontal=True, key="empresa_e_modo")
    cobrar = modo == "cobrar"
    quien = "cliente" if cobrar else "proveedor"
    titulo_seccion(
        "Archivos", 2,
        "El listado de HELISA (<b>Lista de facturas por pagar de "
        "acreedores</b> o <b>Planilla para cobros de clientes</b>) da los "
        "documentos pendientes y su saldo. La <b>programación anterior</b> "
        "de EMPRESA E (PROGR. … #) aporta el NIT, el concepto, el valor inicial, "
        "las observaciones, las secciones de impuestos y seguridad social y "
        "los anticipos.")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga("HELISA", f"Cuentas por {modo}",
                         "Obligatorio · listado .xls de HELISA",
                         "Listado de HELISA con los documentos pendientes "
                         f"por {quien}: documento, fechas y saldo.")
        f_hel = st.file_uploader("Listado HELISA", type=["xls", "xlsx",
                                                         "xml"],
                                 key=f"empresa_e_helisa_{modo}",
                                 label_visibility="collapsed")
    with c2:
        encabezado_carga("ANT", "Programación anterior",
                         "Obligatorio · la última de EMPRESA E (.xls o .xlsx)",
                         "La relación de facturas pendientes anterior "
                         "(RELACION DE FACTURAS PENDIENTES POR "
                         f"{'COBRAR' if cobrar else 'PAGAR'} AL …). Solo se "
                         "lee.")
        f_ant = st.file_uploader("Anterior", type=["xls", "xlsx"],
                                 key=f"empresa_e_anterior_{modo}",
                                 label_visibility="collapsed")
    if not (f_hel and f_ant):
        st.info("Carga los dos archivos para continuar.")
        return
    try:
        with st.spinner("Leyendo los archivos…"):
            helisa, anterior = _leer_entradas_empresa_e(
                f_hel.getvalue(), f_ant.getvalue(), f_ant.name, modo)
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    if helisa.get("clase") and helisa["clase"] != modo:
        st.warning("El listado de HELISA parece de cuentas por "
                   f"{helisa['clase']} y elegiste cuentas por {modo}. Se usa "
                   "tal como se cargó.")
    st.success(f"HELISA: {len(helisa['documentos'])} documentos "
               f"({formato_cop(helisa['total'])}) · Anterior: "
               f"{len(anterior['documentos'])} documentos"
               + (f" al {anterior['fecha']:%d/%m/%Y}" if anterior.get("fecha")
                  else ""))
    titulo_seccion("Fecha y opciones", 3,
                   "La fecha va en el título («RELACION DE FACTURAS "
                   "PENDIENTES … AL …») y en el nombre del archivo.")
    c1, c2 = st.columns([1, 2])
    with c1:
        fecha = st.date_input("Fecha de la programación",
                              value=helisa.get("fecha_corte") or
                              datetime.date.today(), key="empresa_e_fecha",
                              format="DD/MM/YYYY")
    with c2:
        st.write("")
        marcar = st.checkbox(
            "Escribir «FACTURA VENCIDA» / «CUENTA DE COBRO VENCIDA» en los "
            "vencidos sin observación",
            value=variantes[modo].get("marcar_vencidas", True),
            key=f"empresa_e_marcar_{modo}")
    huella = _huella(f_hel.getvalue(), f_ant.getvalue(), fecha, marcar, modo)
    if st.session_state.get("pp_huella") != huella:
        st.session_state["pp_huella"] = huella
        st.session_state["pp_partidas"] = armar_empresa_e(
            helisa, anterior, fecha, modo, marcar)
        st.session_state.pop("pp_archivo", None)
    partidas = st.session_state["pp_partidas"]

    titulo_seccion(
        "Revisión", 4,
        "Cada fila es un documento pendiente en HELISA con lo que se trae "
        "de la anterior. Completa el <b>NIT</b>, el <b>concepto</b> y el "
        "<b>valor inicial</b> de los documentos nuevos (en HELISA solo está "
        "el saldo): la plataforma no los inventa.")
    mostrar = st.toggle("Mostrar también los que salen",
                        key=f"empresa_e_todas_{modo}")
    filas = [{"id": p["id"], "Incluir": p["incluir"],
              "Tercero": p["tercero"], "NIT": p["nit"],
              "Documento": f"{p['tipo']} {p['numero']}",
              "Concepto": p["concepto"],
              "Vence": p["vence"].strftime("%d/%m/%Y") if p.get("vence")
              else (p.get("vence_texto") or ""),
              "Valor inicial": p["valor_inicial"], "Saldo": p["saldo"],
              "Observaciones": p["obs"], "Origen": p["origen"],
              "Revisar": " · ".join(p["revisar"]) or p["motivo"]}
             for p in partidas if mostrar or p["incluir"]]
    if filas:
        editada = st.data_editor(
            pd.DataFrame(filas).set_index("id"),
            key=f"empresa_e_editor_{huella[:10]}_{int(mostrar)}",
            use_container_width=True, height=480, column_config={
                "Incluir": st.column_config.CheckboxColumn(width="small"),
                "Tercero": st.column_config.TextColumn(disabled=True),
                "Documento": st.column_config.TextColumn(disabled=True),
                "Vence": st.column_config.TextColumn(disabled=True),
                "Saldo": st.column_config.NumberColumn(disabled=True,
                                                       format="%.2f"),
                "Valor inicial": st.column_config.NumberColumn(
                    format="%.2f"),
                "Observaciones": st.column_config.TextColumn(width="large"),
                "Origen": st.column_config.TextColumn(disabled=True),
                "Revisar": st.column_config.TextColumn(disabled=True,
                                                       width="large")})
        por_id = {p["id"]: p for p in partidas}
        for ident, f in editada.iterrows():
            p = por_id.get(ident)
            if not p:
                continue
            p["incluir"] = bool(f["Incluir"])
            p["nit"] = "" if str(f["NIT"]) in ("nan", "None") else \
                str(f["NIT"] or "")
            p["concepto"] = "" if str(f["Concepto"]) in ("nan", "None") \
                else str(f["Concepto"] or "")
            p["obs"] = "" if str(f["Observaciones"]) in ("nan", "None") \
                else str(f["Observaciones"] or "")
            try:
                vi = float(f["Valor inicial"])
                p["valor_inicial"] = None if vi != vi else round(vi, 2)
            except (TypeError, ValueError):
                p["valor_inicial"] = None
    _graficos_programacion(partidas, fecha, f"empresa_e_{modo}",
                           "Cliente" if modo == "cobrar" else "Proveedor")
    # v6.14: composicion del total y partidas por confirmar.
    mostrar_diferencias(panel_revision_pagos(partidas, None,
                                             "Programación actual"),
                        f"empresa_e_rev_{modo}")
    r = resumen_empresa_e(partidas, fecha)
    c = st.columns(4)
    c[0].metric("Documentos incluidos", r["incluidas"],
                f"{r['excluidas']} salen", delta_color="off")
    c[1].metric("Clientes" if cobrar else "Proveedores", r["terceros"])
    c[2].metric("Total saldo", formato_cop(r["total"]))
    c[3].metric("Por completar", r["sin_concepto"] + r["sin_valor"],
                "concepto o valor inicial", delta_color="off")
    if r["sin_concepto"] or r["sin_valor"]:
        st.warning(f"{r['sin_concepto']} documento(s) sin concepto y "
                   f"{r['sin_valor']} sin valor inicial: quedan en amarillo "
                   "en el Excel hasta completarlos.")
    manuales = [dict(m, valor=m["saldo"]) for m in anterior["manuales"]]
    for m in manuales + anterior["anticipos"]:
        m.setdefault("fecha_txt", m.get("emision_texto") or
                     m.get("fecha_texto") or "")
    salida_m, salida_a = [], []
    if manuales:
        titulo_seccion("Impuestos y seguridad social", None,
                       "Se copian de la anterior: actualiza valores, "
                       "agrega o quita filas antes de generar.")
        salida_m = _editor_filas_extra(
            manuales, [("Incluir", "incluir"), ("Sección", "seccion"),
                       ("Descripción", "descripcion"),
                       ("Fecha", "fecha_txt"), ("Valor", "valor"),
                       ("Observaciones", "obs")],
            f"empresa_e_man_{huella[:10]}", "Desmarca para no llevarla.")
        originales = {m["descripcion"]: m for m in manuales}
        for m in salida_m:
            m["fecha_texto"] = m.pop("fecha_txt", "")
            base = originales.get(m.get("descripcion")) or {}
            for k in ("nit", "tercero", "valor_inicial"):
                m.setdefault(k, base.get(k))
    if anterior["anticipos"]:
        titulo_seccion("Anticipos pendientes", None,
                       "Bloque de anticipos de la anterior; se copia tal "
                       "cual.")
        salida_a = _editor_filas_extra(
            anterior["anticipos"],
            [("Incluir", "incluir"), ("Tercero", "tercero"),
             ("Documento", "numero"), ("Fecha", "fecha_txt"),
             ("Concepto", "concepto"), ("Valor", "valor"),
             ("Observaciones", "obs")],
            f"empresa_e_ant_{huella[:10]}", "Desmarca para no llevarlo.")
        titulos = {a["numero"]: a for a in anterior["anticipos"]}
        for a in salida_a:
            a["fecha_texto"] = a.pop("fecha_txt", "")
            base = titulos.get(a.get("numero")) or {}
            for k in ("titulo", "nit", "tipo", "valor_inicial"):
                a.setdefault(k, base.get(k))
    titulo_seccion("Generar y descargar", 5,
                   "Genera la relación de facturas pendientes con el formato "
                   "de EMPRESA E. El archivo se descarga: guárdalo tú en la "
                   "carpeta que corresponda.")
    if st.button("Generar programación", type="primary", key="empresa_e_generar",
                 use_container_width=True):
        try:
            contenido = generar_excel_empresa_e(partidas, {
                "fecha": fecha, "modo": modo,
                "empresa": anterior.get("empresa") or empresa["nombre"],
                "manuales": salida_m, "anticipos": salida_a})
            st.session_state["pp_archivo"] = (
                nombre_archivo_empresa_e(modo, fecha), contenido)
        except Exception as error:
            reportar_error("No se pudo generar el archivo", error)
    if st.session_state.get("pp_archivo"):
        nombre, contenido = st.session_state["pp_archivo"]
        st.success(f"Listo: {nombre}")
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary", key="empresa_e_descargar",
            use_container_width=True)


def _flujo_cxp(clave, empresa):
    """Programacion tipo cuentas por pagar con observaciones (EMPRESA D,
    EMPRESA F). v6.10: empresas con variantes (EMPRESA F: por pagar / por
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
        st.session_state["pp_partidas"] = armar_cxp_empresa_d(
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

    _graficos_programacion(partidas, fecha, "cxp",
                           "Cliente" if cobrar else "Proveedor")
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


# ============================================================
# v6.18 · EMPRESA B S.A.S.: flujo de caja + relacion de anticipos
# ============================================================
@_cache_datos
def _leer_entradas_empresa_b(flujo, nombre_flujo, relacion, nombre_rel, informes):
    anterior = EMPRESA_B.leer_flujo_empresa_b(flujo, nombre_flujo)
    rel = EMPRESA_B.leer_relacion_anticipos(relacion, nombre_rel) if relacion \
        else None
    leidos = {"cobrar": None, "pagar": None, "realizados": None,
              "recibidos": None}
    avisos = []
    for nombre, contenido in informes:
        try:
            h = leer_cxp_helisa(contenido)
            leidos[h["clase"]] = h
            continue
        except Exception:
            pass
        try:
            a = EMPRESA_B.leer_anticipos_helisa(contenido)
            leidos[a["clase"]] = a
        except Exception:
            avisos.append(f"{nombre}: no se reconoció como cartera, cuentas "
                          "por pagar ni anticipos de HELISA.")
    return anterior, rel, leidos, avisos


# Grupos de avisos del flujo de EMPRESA B: (texto que contiene, titulo, abierto).
# Primero lo que hay que confirmar; al final lo informativo.
GRUPOS_AVISO_EMPRESA_B = [
    ("sigue pendiente en helisa", "Proyectado en semana pasada y sigue "
     "pendiente: ¿se pagó?", True),
    ("abonos", "Cambió el saldo en HELISA (abonos)", True),
    ("tercero nuevo", "Terceros nuevos: completar NIT y concepto", True),
    ("pago fijo", "Pagos fijos que se corrieron al mes siguiente", True),
    ("valor del anticipo actualizado", "Anticipos con valor actualizado",
     True),
    ("no se incluye", "Terceros que no entran al flujo", False),
    ("figura como", "Documento con otro número en HELISA", False),
    ("semanas pasadas", "Filas de semanas pasadas que se limpian", False),
    ("sale", "Salen (pagados, cruzados o legalizados)", False),
]


def _avisos_empresa_b(alertas, que):
    """Avisos agrupados por tipo, cada grupo en su desplegable."""
    if not alertas:
        return
    grupos = {}
    for a in alertas:
        t = a.lower()
        g = next(((tit, abierto) for clave, tit, abierto in GRUPOS_AVISO_EMPRESA_B
                  if clave in t), ("Otros avisos", True))
        grupos.setdefault(g, []).append(a)
    orden = [(t, ab) for _, t, ab in GRUPOS_AVISO_EMPRESA_B] + [("Otros avisos",
                                                            True)]
    for g in sorted(grupos, key=orden.index):
        items = grupos[g]
        with st.expander(f"{g[0]} · {len(items)} ({que})", expanded=g[1]):
            st.markdown('<ul class="gm-avisos">' + "".join(
                f"<li>{html.escape(a)}</li>" for a in items) + "</ul>",
                unsafe_allow_html=True)


def _config_empresa_b_editable():
    """v6.23: terceros que van por fuera del flujo y anticipos agrupados por
    mes (datos privados del cliente, guardados en GMYA Tools)."""
    import pandas as pd
    config = EMPRESA_B.config_empresa_b()
    with st.expander("Terceros por fuera del flujo y anticipos agrupados por "
                     f"mes ({len(config['terceros_fuera'])} · "
                     f"{len(config['anticipos_por_mes'])})"):
        st.caption("Terceros que no van en el flujo a propósito (socios, "
                   "servicios en pagos fijos): se avisan, no se agregan. "
                   "Anticipos por mes: los de ese NIT se agrupan en una "
                   "fila por mes con el texto indicado ({mes} y {anio} se "
                   "reemplazan).")
        c1, c2 = st.columns(2)
        fuera = c1.data_editor(
            pd.DataFrame({"Tercero": config["terceros_fuera"] or [""]}),
            num_rows="dynamic", hide_index=True, use_container_width=True,
            key="empresa_b_cfg_fuera")
        por_mes = c2.data_editor(
            pd.DataFrame([{"NIT": k, "Texto": v} for k, v in
                          config["anticipos_por_mes"].items()] or
                         [{"NIT": "", "Texto": ""}]),
            num_rows="dynamic", hide_index=True, use_container_width=True,
            key="empresa_b_cfg_mes")
        nuevos_fuera = [str(t).strip() for t in fuera["Tercero"]
                        if t is not None and str(t).strip()]
        nuevos_mes = {str(r["NIT"]).strip(): str(r["Texto"]).strip()
                      for _, r in por_mes.iterrows()
                      if r["NIT"] is not None and str(r["NIT"]).strip()
                      and r["Texto"] is not None and str(r["Texto"]).strip()}
        config = dict(config, terceros_fuera=nuevos_fuera,
                      anticipos_por_mes=nuevos_mes)
        if st.button("Guardar para las próximas veces",
                     key="empresa_b_cfg_guardar"):
            try:
                donde = EMPRESA_B.guardar_config_empresa_b(nuevos_fuera, nuevos_mes)
                st.success(f"Guardado en {donde}.")
            except Exception as error:
                reportar_error("No se pudo guardar", error)
    return config


def _flujo_empresa_b(clave, empresa):
    """Flujo de caja semanal y relacion de anticipos de EMPRESA B S.A.S."""
    import pandas as pd
    titulo_seccion(
        "Archivos", 2,
        "El <b>flujo de caja anterior</b> y la <b>relación de anticipos "
        "anterior</b> aportan el formato, los conceptos, las observaciones, "
        "lo proyectado y los pagos fijos. Los <b>informes de HELISA</b> "
        "(cartera, cuentas por pagar, anticipos realizados y anticipos "
        "recibidos) dicen qué sigue pendiente. Los informes se reconocen "
        "solos: cárgalos juntos en cualquier orden.")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga("ANT", "Flujo de caja anterior",
                         "Obligatorio · FLUJO DE CAJA V…. EMPRESA B S.A.S. .xlsx",
                         "El último flujo de caja de EMPRESA B. Solo se lee; el "
                         "nuevo sale con el mismo formato.")
        f_flujo = st.file_uploader("Flujo anterior", type=["xlsx"],
                                   key="empresa_b_flujo",
                                   label_visibility="collapsed")
    with c2:
        encabezado_carga("ANT", "Relación de anticipos anterior",
                         "Opcional · RELACION DE ANTICIPOS … #n .xlsx",
                         "Anticipos girados y recibidos pendientes por "
                         "legalizar de la vez anterior.")
        f_rel = st.file_uploader("Relación anterior", type=["xlsx"],
                                 key="empresa_b_rel", label_visibility="collapsed")
    encabezado_carga("HELISA", "Informes de HELISA",
                     "Cartera · Cuentas por pagar · Anticipos realizados · "
                     "Anticipos recibidos (.xls)",
                     "Tal como salen de HELISA: Planilla para cobros de "
                     "clientes, Lista de facturas por pagar de acreedores y "
                     "los dos informes de anticipos (VR.ANTICIPO, "
                     "VR.APLICADO, VR.POR APLICAR).")
    f_inf = st.file_uploader("Informes HELISA", type=["xls", "xlsx", "xml"],
                             accept_multiple_files=True, key="empresa_b_informes",
                             label_visibility="collapsed")
    if not f_flujo:
        st.info("Carga el flujo de caja anterior y los informes de HELISA "
                "para continuar.")
        return
    try:
        with st.spinner("Leyendo los archivos…"):
            anterior, rel, leidos, avisos = _leer_entradas_empresa_b(
                f_flujo.getvalue(), f_flujo.name,
                f_rel.getvalue() if f_rel else None,
                f_rel.name if f_rel else "",
                tuple((f.name, f.getvalue()) for f in (f_inf or [])))
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    for a in avisos:
        st.warning(a)
    nombres = {"cobrar": "Cartera", "pagar": "Cuentas por pagar",
               "realizados": "Anticipos realizados",
               "recibidos": "Anticipos recibidos"}
    kpis([{"etiqueta": nombres[k], "valor": (
        f"{len(v['documentos'] if 'documentos' in v else v['docs'])} doc."
        if v else "Falta"), "icono": "archivo",
        "tono": "teal" if v else "ambar",
        "estado": "ok" if v else "alerta",
        "estado_texto": "Cargado" if v else "Falta"}
        for k, v in leidos.items()])

    titulo_seccion(
        "Semanas y saldos", 3,
        "Semanas de lunes a domingo; la primera es la que contiene la fecha "
        "del flujo. El <b>saldo inicial</b> de cada cuenta se propone con "
        "el saldo proyectado de la última semana que ya pasó en el flujo "
        "anterior: cámbialo por el saldo real del banco si lo tienes.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        fecha = st.date_input("Fecha del flujo", value=datetime.date.today(),
                              format="DD/MM/YYYY", key="empresa_b_fecha")
    with c2:
        n_sem = st.number_input("Semanas", min_value=2, max_value=8, value=4,
                                step=1, key="empresa_b_semanas")
    propuesto = EMPRESA_B.saldo_inicial_propuesto(anterior, fecha)
    saldos = {}
    for j, col in enumerate((c3, c4)):
        with col:
            saldos[j] = st.number_input(
                f"Saldo inicial {anterior['cuentas'][j].title()}",
                value=float(propuesto[j]), step=1000.0,
                format="%.2f", key=f"empresa_b_saldo_{j}_{fecha}")
    config = _config_empresa_b_editable()
    # Copia: lo leido esta en cache y la tabla de nuevos se edita encima.
    import copy
    res = EMPRESA_B.armar_flujo_empresa_b(copy.deepcopy(anterior), leidos["cobrar"],
                                leidos["pagar"], fecha, int(n_sem), saldos,
                                config=config)
    modelo = res["modelo"]
    etiquetas = ["Sin semana"] + [EMPRESA_B.etiqueta_semana(a, b)
                                  for a, b in modelo["semanas"]]

    titulo_seccion(
        "Documentos nuevos", 4,
        "Documentos que aparecieron en HELISA. La semana se propone por la "
        "fecha de vencimiento (si vence después de la última semana queda "
        "sin semana) y la cuenta por la que usa ese tercero. Completa el "
        "<b>concepto</b> y el <b>NIT</b> de los terceros nuevos (en "
        "amarillo en el Excel si quedan vacíos).")
    if res["nuevos"]:
        filas = []
        for i, (tipo, g, f) in enumerate(res["nuevos"]):
            k = next(iter(f["proy"]), (None, 0))
            filas.append({
                "id": i, "Sección": "Cartera" if tipo == "cxc" else
                "Por pagar", "Tercero": g["nombre"],
                "NIT": "" if g.get("nit") in (None, "") else str(g["nit"]),
                "Documento": f["celdas"].get("D") or f["celdas"].get("C"),
                "Vence": f["helisa"]["vence"].strftime("%d/%m/%Y")
                if f["helisa"].get("vence") else "",
                "Valor": f["h"], "Concepto": f["celdas"].get("E") or "",
                "Semana": etiquetas[k[0] + 1] if k[0] is not None else
                etiquetas[0],
                "Cuenta": modelo["cuentas"][k[1]]})
        editada = st.data_editor(
            pd.DataFrame(filas).set_index("id"), key=f"empresa_b_nuevos_{fecha}",
            use_container_width=True, column_config={
                "Sección": st.column_config.TextColumn(disabled=True),
                "Tercero": st.column_config.TextColumn(disabled=True),
                "Documento": st.column_config.TextColumn(disabled=True),
                "Vence": st.column_config.TextColumn(disabled=True),
                "Valor": st.column_config.NumberColumn(disabled=True,
                                                       format="%.2f"),
                "Concepto": st.column_config.TextColumn(width="large"),
                "Semana": st.column_config.SelectboxColumn(
                    options=etiquetas, required=True),
                "Cuenta": st.column_config.SelectboxColumn(
                    options=modelo["cuentas"], required=True)})
        for i, fila in editada.iterrows():
            tipo, g, f = res["nuevos"][int(i)]
            f["celdas"]["E"] = str(fila["Concepto"] or "").strip()
            nit = str(fila["NIT"] or "").strip()
            if nit and nit not in ("nan", "None"):
                g["nit"] = int(nit) if nit.isdigit() else nit
            k = etiquetas.index(fila["Semana"]) - 1
            j = modelo["cuentas"].index(fila["Cuenta"])
            f["proy"] = {(k, j): (f["h"], True)} if k >= 0 else {}
        res["resumen"] = EMPRESA_B.calcular_totales(modelo)
    else:
        st.success("No hay documentos nuevos en HELISA.")

    titulo_seccion(
        "Resultado", 5,
        "Saldo proyectado de cada cuenta al cierre de cada semana y lo que "
        "entra y sale. Los totales son los mismos que calculan las fórmulas "
        "del Excel.")
    r = res["resumen"]
    n = len(modelo["semanas"])
    fin = [r["saldo"][(n - 1, j)] for j in (0, 1)]
    kpis([{"etiqueta": f"Saldo {modelo['cuentas'][j].title()} al "
           f"{modelo['semanas'][-1][1]:%d/%m}", "valor": formato_cop(fin[j]),
           "icono": "banco", "tono": "verde" if fin[j] >= 0 else "ambar",
           "estado": "ok" if fin[j] >= 0 else "alerta",
           "estado_texto": "Alcanza" if fin[j] >= 0 else "Sobregiro"}
          for j in (0, 1)] + [
        {"etiqueta": "Documentos nuevos", "valor": str(len(res["nuevos"])),
         "icono": "documentos", "tono": "indigo"},
        {"etiqueta": "Avisos para revisar", "valor": str(len(res["alertas"])),
         "icono": "alerta", "tono": "ambar" if res["alertas"] else "verde"}])
    filas_sem = []
    for k, (a, b) in enumerate(modelo["semanas"]):
        entra = sum(r["ingresos"][(k, j)] + r["cxc"][(k, j)] for j in (0, 1))
        sale = sum(r["cxp"][(k, j)] + r["anticipos"][(k, j)] for j in (0, 1))
        filas_sem.append((EMPRESA_B.etiqueta_semana(a, b), round(entra, 2),
                          round(sale, 2)))
    g1, g2 = st.columns(2)
    with g1:
        grafico("Entradas vs salidas por semana", html_comparativo(
            filas_sem, "Entradas (ingresos + cartera)", "Salidas (pagos + "
            "anticipos)", color_a="#5FD3CB", color_b="#E0118F",
            texto_diferencia=lambda d: f"Neto {pesos(d)}",
            ok_si=lambda d: d >= 0), icono_nombre="calendario")
    with g2:
        grafico("Saldo proyectado al cierre de cada semana", html_comparativo(
            [(EMPRESA_B.etiqueta_semana(a, b), r["saldo"][(k, 0)],
              r["saldo"][(k, 1)]) for k, (a, b) in
             enumerate(modelo["semanas"])], modelo["cuentas"][0].title(),
            modelo["cuentas"][1].title(), color_a="#8B95F5",
            color_b="#E0118F", texto_diferencia=lambda d: "",
            ok_si=lambda d: True), icono_nombre="banco")
    _avisos_empresa_b(res["alertas"], "flujo")

    rel_res = None
    if rel:
        rel_res = EMPRESA_B.armar_relacion_anticipos(
            rel, leidos["realizados"], leidos["recibidos"], config=config)
        rs = rel_res["resumen"]
        titulo_seccion(
            "Relación de anticipos", 6,
            "Solo los anticipos que HELISA trae <b>por aplicar</b>. El total "
            "de cada sección debe ser igual al VR.POR APLICAR de HELISA.")
        kp = []
        for k, et in (("realizados", "Anticipos girados"),
                      ("recibidos", "Anticipos recibidos")):
            if k in rs:
                ok = abs(rs[k]["total"] - rs[k]["helisa"]) < .005
                kp.append({"etiqueta": et, "valor": formato_cop(rs[k]["total"]),
                           "icono": "dinero", "tono": "verde" if ok else
                           "ambar", "estado": "ok" if ok else "alerta",
                           "estado_texto": "= HELISA" if ok else "≠ HELISA",
                           "detalle": f"{rs[k]['nuevos']} nuevos · HELISA "
                           f"{formato_cop(rs[k]['helisa'])}"})
        kpis(kp, columnas=2)
        _avisos_empresa_b(rel_res["alertas"], "relación")

    titulo_seccion("Generar y descargar", 7,
                   "Los archivos salen con el mismo formato de los "
                   "anteriores y fórmulas (totales por tercero, por sección, "
                   "saldo por semana). Se descargan: guárdalos tú en la "
                   "carpeta de EMPRESA B.")
    if st.button("Generar flujo de caja" + (" y relación de anticipos"
                                            if rel_res else ""),
                 type="primary", key="empresa_b_generar",
                 use_container_width=True):
        try:
            with st.spinner("Armando los archivos…"):
                salida = [(EMPRESA_B.nombre_flujo(f_flujo.name, fecha),
                           EMPRESA_B.excel_flujo_empresa_b(res, f_flujo.getvalue()))]
                if rel_res:
                    salida.append((EMPRESA_B.nombre_relacion(
                        f_rel.name, rel["numero"]),
                        EMPRESA_B.excel_relacion_anticipos(rel_res,
                                                      f_rel.getvalue())))
            st.session_state["empresa_b_archivos"] = salida
        except Exception as error:
            reportar_error("No se pudieron generar los archivos", error)
    for i, (nombre, contenido) in enumerate(
            st.session_state.get("empresa_b_archivos") or []):
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary",
            key=f"empresa_b_descargar_{i}", use_container_width=True)
