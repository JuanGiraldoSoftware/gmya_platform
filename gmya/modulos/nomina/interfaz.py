"""Pantalla "Pagos de nomina" (Streamlit). Contrato: modulo_nomina().

Depende de: gmya.comun.numeros, gmya.comun.cache, gmya.ui.componentes, gmya.modulos.nomina.logica, gmya.modulos.nomina.empresa_a, gmya.registro.interfaz
"""

import datetime
import re
from collections import OrderedDict

import streamlit as st

from gmya.comun.numeros import formato_cop
from gmya.comun.cache import _cache, _huella
from gmya.ui.diferencias import mostrar_diferencias
from gmya.modulos.nomina.diferencias import (
    panel_conciliacion_nomina, panel_controles_ne, panel_nomina_banco,
)
from gmya.comun.estadistica import top_n
from gmya.ui.visual import grafico, html_barras, html_barras_valor, kpis
from gmya.ui.componentes import (
    banner_modulo, encabezado_carga, _glosario_pp, titulo_seccion,
)
from gmya.modulos.nomina.logica import (
    actualizar_valores_xlsx, alertas_nomina, codigo_descripcion_nomina,
    cruzar_nomina, fecha_aplicacion_numero, leer_formato_pagos,
    leer_planilla_nomina, MESES_NOMINA, MESES_NOMINA_NOMBRE,
    periodo_de_planillas,
)
from gmya.modulos.nomina.empresa_a import (
    alertas_nomina_empresa_a, cruzar_nomina_empresa_a, leer_base_nomina_empresa_a,
    leer_planilla_nomina_empresa_a, leer_vacaciones_empresa_a,
)
from gmya.modulos.nomina.electronica import (
    armar_nomina_electronica, excel_nomina_electronica,
    excel_nomina_electronica_subir, leer_acumulado_ne,
    leer_anterior_ne, leer_movimiento_ne,
)
import gmya.modulos.nomina.facturacion as FAC
from gmya.modulos.nomina.conciliacion import (
    conciliar_nomina, excel_conciliacion_nomina, GRUPOS,
    leer_acumulado_nomina, leer_balance_nomina, leer_liquidacion_nomina,
)
from gmya.registro.interfaz import reportar_error
from gmya.registro.privados import guardar_privado, leer_privado

ARCHIVO_CARGOS_FAC = "facturacion_cargos"


# ============================================================
# INTERFAZ: PAGOS DE NOMINA
# ============================================================
ESTADOS_NOMINA = {
    "ok": "✔ Cédula y nombre coinciden",
    "nombre": "⚠ Cédula igual, nombre distinto",
    "sin_planilla": "⚠ No está en ninguna planilla",
    "repetido": "⚠ Cédula repetida en el Excel",
}

GLOSARIO_NOMINA = [
    ("Valor actual", "Lo que tiene hoy la columna <b>ValorTransaccion</b> "
                     "del Excel del banco para ese empleado."),
    ("Valor planillas", "Suma de lo que aparece en <b>todas</b> las "
                        "planillas cargadas para esa cédula (nómina, prima, "
                        "vacaciones…). Es el valor que queda en el Excel."),
    ("Coincidencia", "Qué tanto se parece el nombre del Excel al de la "
                     "planilla (el Excel suele traer nombres recortados o "
                     "con errores de digitación). Por debajo de 75 % no se "
                     "actualiza sin tu confirmación."),
    ("Actualizar", "Marcado: el valor de la planilla reemplaza el del Excel. "
                   "Para las filas con nombre distinto, márcalo solo si "
                   "confirmas que es la misma persona."),
]


@_cache
def _leer_planilla_nomina_cache(contenido, nombre):
    return leer_planilla_nomina(contenido, nombre)


@_cache
def _leer_formato_pagos_cache(contenido):
    return leer_formato_pagos(contenido)


FORMATOS_NOMINA = OrderedDict([
    ("banco", "Formato de pagos del banco (FORMATOPAB · p. ej. EMPRESA C)"),
    ("empresa_a", "Base de datos de nómina EMPRESA A (neto + vacaciones)"),
    # v6.11: plantilla de carga de la nomina electronica (DIAN).
    ("electronica", "Nómina electrónica (plantilla DIAN · p. ej. EMPRESA G, "
                    "EMPRESA H)"),
    # v6.10: conciliacion (no actualiza ningun archivo).
    ("conciliacion", "Conciliación de nómina (HELISA vs liquidación vs "
                     "contabilidad · p. ej. EMPRESA D)"),
    # v6.21: facturacion por horas (no actualiza ningun archivo).
    ("facturacion", "Facturación por horas EMPRESA A (días PILA × tarifa por "
                    "colaborador)"),
])


@_cache
def _leer_planilla_hib_cache(contenido, nombre):
    return leer_planilla_nomina_empresa_a(contenido, nombre)


@_cache
def _leer_vacaciones_hib_cache(contenido, nombre):
    return leer_vacaciones_empresa_a(contenido, nombre)


@_cache
def _leer_base_hib_cache(contenido):
    return leer_base_nomina_empresa_a(contenido)


@_cache
def _leer_ne_cache(acu, mov, ant):
    return (leer_acumulado_ne(acu), leer_movimiento_ne(mov),
            leer_anterior_ne(ant) if ant else {})


def _flujo_nomina_electronica():
    """v6.11: arma la plantilla de carga de la nomina electronica con el
    acumulado de nomina de HELISA y el movimiento contable del mes (como
    el archivo trabajado de la firma). Las fechas de ingreso salen del
    archivo trabajado anterior o se escriben en la tabla."""
    import calendar
    import pandas as pd
    titulo_seccion(
        "Archivos", 1,
        "El <b>acumulado de nómina por concepto y periodo</b> (módulo de "
        "nómina de HELISA) y el <b>movimiento de prueba</b> de las cuentas "
        "del gasto y costo de nómina son obligatorios. El <b>archivo "
        "trabajado anterior</b> (opcional) aporta las fechas de ingreso de "
        "los empleados, que HELISA no trae. Carga los archivos <b>tal como "
        "salen de HELISA</b>: no hace falta quitar columnas, ordenar ni "
        "cambiar signos.")
    c1, c2, c3 = st.columns(3)
    with c1:
        encabezado_carga(
            "HELISA", "Acumulado de nómina", "Obligatorio · .xls",
            "Original de HELISA (o el trabajado). Acumulado por concepto y periodo: IDENTIFICACION, CONCEPTO, "
            "BASE, CANTIDAD, ValorPago. De aquí salen los días, las horas, "
            "las bases y las deducciones (salud, pensión, fondo de "
            "solidaridad, préstamos, retención).")
        f_acu = st.file_uploader("Acumulado", type=["xls", "xlsx", "xml"],
                                 key="ne_acumulado",
                                 label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "MOV", "Balance / movimiento", "Obligatorio · .xlsx o .xls",
            "Balance de las cuentas 5105 y 7205 (original de HELISA o el "
            "trabajado). Movimiento de prueba con terceros de las cuentas de nómina (51 "
            "gasto, 72/61 costo). De aquí salen los devengados del mes: "
            "sueldo, auxilios, horas extras, incapacidades y las "
            "provisiones (vacaciones, prima, cesantías e intereses).")
        f_mov = st.file_uploader("Movimiento", type=["xls", "xlsx", "xml"],
                                 key="ne_movimiento",
                                 label_visibility="collapsed")
    with c3:
        encabezado_carga(
            "ANT", "Archivo trabajado anterior", "Opcional · .xlsx",
            "El último layout de carga (LayoutNominaCargaMasiva … a subir) o "
            "ARCHIVO DE NOMINA ELECTRONICA … TRABAJADO de la empresa: se toman las fechas de ingreso (hoja BASE DE DATOS o "
            "la plantilla). Solo se lee.")
        f_ant = st.file_uploader("Anterior", type=["xlsx"],
                                 key="ne_anterior",
                                 label_visibility="collapsed")
    if not (f_acu and f_mov):
        st.info("Carga el acumulado de nómina y el movimiento contable para "
                "continuar.")
        return
    try:
        with st.spinner("Leyendo los archivos…"):
            acumulado, movimiento, fechas = _leer_ne_cache(
                f_acu.getvalue(), f_mov.getvalue(),
                f_ant.getvalue() if f_ant else b"")
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    fechas = {k: dict(v) for k, v in fechas.items()}
    st.success(f"Acumulado: {len(acumulado['empleados'])} empleados · "
               f"Movimiento: {len(movimiento['terceros'])} terceros"
               + (f" · Anterior: {len(fechas)} fechas de ingreso"
                  if fechas else ""))

    titulo_seccion(
        "Periodo y fechas", 2,
        "Periodo de la nómina (fecha inicio y fin de liquidación), fecha de "
        "emisión del documento y fecha de pago (por defecto, el último día "
        "del periodo, igual para todos).")
    hoy = datetime.date.today()
    base = (acumulado.get("fechas_pago") or [hoy.replace(day=1) -
                                             datetime.timedelta(days=1)])[-1]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mes = st.selectbox("Mes", list(range(1, 13)), index=base.month - 1,
                           format_func=lambda m: MESES_NOMINA_NOMBRE[m - 1]
                           .capitalize(), key="ne_mes")
    with c2:
        anio = st.number_input("Año", 2020, 2100, base.year, key="ne_anio")
    inicio = datetime.date(int(anio), mes, 1)
    fin = datetime.date(int(anio), mes,
                        calendar.monthrange(int(anio), mes)[1])
    with c3:
        emision = st.date_input("Fecha de emisión", value=hoy,
                                key="ne_emision", format="DD/MM/YYYY")
    with c4:
        pago = st.date_input("Fecha de pago", value=fin, key="ne_pago",
                             format="DD/MM/YYYY")

    faltan = [(c, e["nombre"]) for c, e in acumulado["empleados"].items()
              if not (fechas.get(c) or {}).get("fecha_ingreso")]
    if faltan:
        titulo_seccion(
            "Fechas de ingreso que faltan", 3,
            "Estos empleados no tienen fecha de ingreso en el archivo "
            "anterior. Escríbela aquí (la plantilla la necesita para el "
            "tiempo laborado).")
        tabla = pd.DataFrame([{"Cédula": c, "Empleado": n,
                               "Fecha de ingreso": None} for c, n in faltan])
        editada = st.data_editor(
            tabla, key=f"ne_fechas_{_huella(*[c for c, _ in faltan])[:8]}",
            hide_index=True, use_container_width=True, column_config={
                "Cédula": st.column_config.TextColumn(disabled=True),
                "Empleado": st.column_config.TextColumn(disabled=True),
                "Fecha de ingreso": st.column_config.DateColumn(
                    format="DD/MM/YYYY")})
        for _, fila in editada.iterrows():
            f = fila["Fecha de ingreso"]
            if f is not None and str(f) not in ("NaT", "nan", "None"):
                if hasattr(f, "date") and not isinstance(f, datetime.date):
                    f = f.date()
                elif hasattr(f, "to_pydatetime"):
                    f = f.to_pydatetime().date()
                fechas[fila["Cédula"]] = {"fecha_ingreso": f,
                                          "fecha_retiro": None}

    resultado = armar_nomina_electronica(
        acumulado, movimiento, fechas,
        {"inicio": inicio, "fin": fin, "fecha_emision": emision,
         "fecha_pago": pago})
    # v6.13: indicadores del archivo armado.
    def _suma(letra):
        return sum(float(f["fila"].get(letra) or 0) for f in resultado["filas"]
                   if isinstance(f["fila"].get(letra), (int, float)))
    cuadran = sum(1 for c in resultado["controles"]
                  if abs(c["diferencia"]) <= 0.005)
    kpis([
        {"etiqueta": "Empleados", "valor": len(resultado["filas"]),
         "icono": "personas", "tono": "indigo"},
        {"etiqueta": "Devengados", "valor": formato_cop(_suma("DT")),
         "icono": "dinero", "tono": "teal"},
        {"etiqueta": "Deducciones", "valor": formato_cop(_suma("DU")),
         "icono": "balanza", "tono": "ambar"},
        {"etiqueta": "Controles", "valor": f"{cuadran} de "
         f"{len(resultado['controles'])}", "icono": "escudo",
         "tono": "verde" if resultado["cuadra"] else "ambar",
         "estado": "ok" if resultado["cuadra"] else "alerta",
         "detalle": f"{len(resultado['alertas'])} alerta(s) por revisar"
         if resultado["alertas"] else "Sin alertas"},
    ])
    titulo_seccion(
        "Control", 4,
        "Total de cada columna de la plantilla contra la contabilidad "
        "(devengados) o el acumulado de HELISA (deducciones). La "
        "diferencia debe ser 0.")
    mostrar_diferencias(panel_controles_ne(resultado), "ne_dif")
    # v6.16: de que se compone la nomina del mes (columnas de la plantilla).
    from gmya.modulos.nomina.electronica import DEDUCCIONES
    ded = set(DEDUCCIONES)
    deveng = [(c["concepto"], c["plantilla"]) for c in resultado["controles"]
              if c["columna"] not in ded and c["plantilla"]]
    deduc = [(c["concepto"], c["plantilla"]) for c in resultado["controles"]
             if c["columna"] in ded and c["plantilla"]]
    g1, g2 = st.columns(2)
    with g1:
        grafico("Devengados por concepto", html_barras_valor(
            top_n(deveng, 8)), icono_nombre="dinero")
    with g2:
        grafico("Deducciones por concepto", html_barras_valor(
            top_n(deduc, 8)), icono_nombre="balanza")
    with st.expander("Tabla de controles por columna"):
        st.dataframe(pd.DataFrame([{
            "Columna": c["columna"], "Concepto": c["concepto"],
            "Plantilla": c["plantilla"], "Fuente": c["fuente"],
            "Origen": c["origen"], "Diferencia": c["diferencia"]}
            for c in resultado["controles"]]), hide_index=True,
            use_container_width=True)
    if resultado["cuadra"]:
        st.success("Todas las columnas cuadran con la contabilidad y el "
                   "acumulado.")
    if resultado["alertas"]:
        st.warning("**Para revisar:**\n\n" + "\n".join(
            f"- {a}" for a in resultado["alertas"][:20]))
    with st.expander("Vista previa de la plantilla"):
        st.dataframe(pd.DataFrame([{
            "Cédula": f["cedula"], "Empleado": f["nombre"],
            "Días": f["fila"].get("W"), "Sueldo": f["fila"].get("X"),
            "Devengados": f["fila"].get("DT"),
            "Deducciones": f["fila"].get("DU"),
            "Neto": f["fila"].get("DV")} for f in resultado["filas"]]),
            hide_index=True, use_container_width=True)

    titulo_seccion("Descargar", 5,
                   "<b>Archivo para subir</b>: el layout de carga "
                   "(una fila por empleado, solo valores). "
                   "<b>Excel de control</b>: la misma plantilla con las filas "
                   "de control (diferencia en 0) y las hojas CONTROL, BASE "
                   "DE DATOS y ALERTAS.")
    empresa = st.text_input(
        "Empresa (para el nombre del archivo)",
        value=movimiento.get("empresa") or "", key="ne_empresa",
        placeholder="p. ej. EMPRESA G")
    nombre = ("NOMINA ELECTRONICA "
              + MESES_NOMINA_NOMBRE[mes - 1].upper() + f" {int(anio)} "
              + (empresa.split(" S.A.S")[0].split(" SAS")[0]
                 if empresa else "")).strip() + ".xlsx"
    try:
        subir = excel_nomina_electronica_subir(resultado)
        contenido = excel_nomina_electronica(resultado, {})
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Archivo para subir (layout de carga)", subir,
                file_name="LayoutNominaCargaMasiva " + nombre,
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet", type="primary",
                key="ne_descargar_subir", use_container_width=True,
                help="Tu layout de carga tal cual (encabezado y formato), "
                     "con los datos en valores y la columna DW validada "
                     "(OK o REVISAR), sin fórmulas ni filas de control.")
        with d2:
            st.download_button(
                "Excel de control", contenido,
                file_name="CONTROL " + nombre,
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet",
                key="ne_descargar", use_container_width=True,
                help="La misma plantilla con las filas TOTAL / CONTROL / "
                     "DIFERENCIA y las hojas CONTROL, BASE DE DATOS y "
                     "ALERTAS, para revisar antes de subir.")
    except Exception as error:
        reportar_error("No se pudo armar la plantilla", error)


@_cache
def _leer_conciliacion_cache(acu, liq, bal):
    acumulado = leer_acumulado_nomina(acu)
    liquidacion = leer_liquidacion_nomina(liq) if liq else None
    balance = leer_balance_nomina(bal) if bal else None
    return acumulado, liquidacion, balance


def _flujo_conciliacion_nomina():
    """v6.10: concilia lo pagado (acumulado de nomina de HELISA) con la
    liquidacion de nomina en Excel y con la contabilidad (balance de
    prueba). Solo lee: no modifica ningun archivo."""
    titulo_seccion(
        "Archivos", 1,
        "El <b>acumulado de nómina de HELISA</b> es obligatorio. Carga "
        "además la <b>liquidación de nómina</b> (Excel de la firma, p. ej. "
        "NOMINA ELECTRONICA …) y/o el <b>balance de prueba</b> con terceros "
        "de las cuentas de nómina (51/61). Se concilia por cédula y por "
        "concepto, al centavo.")
    c1, c2, c3 = st.columns(3)
    with c1:
        encabezado_carga(
            "HELISA", "Acumulado de nómina", "Obligatorio · .xls de HELISA",
            "Informe de HELISA con una fila por empleado y concepto "
            "(IDENTIFICACION, CONCEPTO, NATURALEZA, ValorPago): es lo que "
            "realmente se <b>pagó</b> y se <b>descontó</b>.")
        f_acu = st.file_uploader("Acumulado de nómina",
                                 type=["xls", "xlsx", "xml"],
                                 key="conc_nom_acumulado",
                                 label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "XLS", "Liquidación de nómina", "Opcional · Excel",
            "El Excel de liquidación / nómina electrónica: una fila por "
            "empleado (CEDULA, NOMBRE) y una columna por concepto, con TOTAL "
            "DEVENGOS, TOTAL DESCUENTOS y NETO A PAGAR.")
        f_liq = st.file_uploader("Liquidación de nómina",
                                 type=["xls", "xlsx", "xml"],
                                 key="conc_nom_liquidacion",
                                 label_visibility="collapsed")
    with c3:
        encabezado_carga(
            "BAL", "Balance de prueba", "Opcional · .xls o PDF de HELISA",
            "Balance de prueba del mes con terceros de las cuentas de "
            "nómina (51 gasto, 61 costo): se toman los débitos − créditos "
            "del mes por empleado.")
        f_bal = st.file_uploader("Balance de prueba",
                                 type=["xls", "xlsx", "xml", "pdf"],
                                 key="conc_nom_balance",
                                 label_visibility="collapsed")
    if not f_acu:
        st.info("Carga el acumulado de nómina de HELISA para continuar.")
        return
    if not (f_liq or f_bal):
        st.info("Carga también la liquidación de nómina y/o el balance de "
                "prueba para tener contra qué conciliar.")
        return
    try:
        with st.spinner("Leyendo los archivos…"):
            acumulado, liquidacion, balance = _leer_conciliacion_cache(
                f_acu.getvalue(), f_liq.getvalue() if f_liq else b"",
                f_bal.getvalue() if f_bal else b"")
        resultado = conciliar_nomina(acumulado, liquidacion, balance)
    except Exception as error:
        reportar_error("No se pudo conciliar la nómina", error)
        return
    empresa = (balance or {}).get("empresa") or ""
    fechas = acumulado.get("fechas_pago") or []
    periodo = (f"Pagos del {fechas[0]:%d/%m/%Y} al {fechas[-1]:%d/%m/%Y}"
               if fechas else "")
    st.success(
        f"Acumulado HELISA: {len(acumulado['empleados'])} empleados"
        + (f" · {periodo}" if periodo else "")
        + (f" · Liquidación: {len(liquidacion['empleados'])} empleados"
           if liquidacion else "")
        + (" · Balance: {} terceros con movimiento de nómina".format(
            sum(1 for v in balance["empleados"].values()
                if any(abs(x) > 0.005 for x in v.values())))
           if balance else ""))

    titulo_seccion(
        "Resultado por concepto", 2,
        "<b>Pagos</b> y <b>descuentos</b>: se compara lo pagado en HELISA "
        "con la liquidación y la contabilidad. <b>Prestaciones</b> "
        "(cesantías, intereses, prima, vacaciones): la liquidación y la "
        "contabilidad registran la <b>provisión</b> del mes, mientras el "
        "acumulado de HELISA trae lo <b>pagado</b> (p. ej. una liquidación "
        "definitiva); por eso se comparan liquidación vs contabilidad. "
        "Tolerancia 0: los centavos se marcan.")
    import pandas as pd
    tabla = pd.DataFrame([{
        "Grupo": GRUPOS[r["grupo"]], "Concepto": r["nombre"],
        "HELISA (pagado)": r["acumulado"],
        "Liquidación": r["liquidacion"] if resultado["tiene_liquidacion"]
        else None,
        "Contabilidad": r["contabilidad"] if resultado["tiene_balance"] and
        r["grupo"] != "descuento" else None,
        "Estado": r["estado"]} for r in resultado["resumen"]])
    st.dataframe(tabla, use_container_width=True, hide_index=True,
                 column_config={c: st.column_config.NumberColumn(
                     format="%.2f") for c in ("HELISA (pagado)",
                                              "Liquidación",
                                              "Contabilidad")})
    if resultado["cuadra"]:
        st.success("Todos los conceptos cuadran al centavo.")
    # v6.14: de donde sale la diferencia, por grupo de conceptos.
    mostrar_diferencias(panel_conciliacion_nomina(resultado), "concnom_dif")
    if resultado["netos"] and resultado["tiene_liquidacion"]:
        titulo_seccion(
            "Neto pagado vs NETO A PAGAR del Excel", 3,
            "El neto realmente pagado (HELISA: pagos − descuentos) contra el "
            "NETO A PAGAR de la liquidación. Si la liquidación suma la "
            "provisión de prestaciones, su neto no es lo que se transfiere.")
        st.dataframe(pd.DataFrame([{
            "Cédula": n["cedula"], "Empleado": n["nombre"],
            "Neto pagado (HELISA)": n["pagado"],
            "NETO A PAGAR (Excel)": n["neto_liquidacion"],
            "Diferencia": None if n["neto_liquidacion"] is None else
            round(n["neto_liquidacion"] - n["pagado"], 2),
            "Explicación": n["explicacion"]} for n in resultado["netos"]]),
            use_container_width=True, hide_index=True)
    if resultado["alertas"]:
        st.warning("**Para revisar:**\n\n" + "\n".join(
            f"- {a}" for a in resultado["alertas"][:25])
            + (f"\n- … y {len(resultado['alertas']) - 25} más (hoja "
               "ALERTAS del Excel)." if len(resultado["alertas"]) > 25
               else ""))
    with st.expander("Detalle por empleado y concepto"):
        st.dataframe(pd.DataFrame([{
            "Cédula": f["cedula"], "Empleado": f["nombre"],
            "Concepto": f["nombre_concepto"],
            "HELISA": f["acumulado"], "Liquidación": f["liquidacion"],
            "Contabilidad": f["contabilidad"], "Estado": f["estado"]}
            for f in resultado["filas"]]), use_container_width=True,
            hide_index=True)

    titulo_seccion("Descargar", 4,
                   "Excel con las hojas RESUMEN, POR EMPLEADO, NETOS y "
                   "ALERTAS. Se entrega siempre, cuadre o no.")
    try:
        contenido = excel_conciliacion_nomina(
            resultado, {"empresa": empresa, "periodo": periodo})
        nombre = ("CONCILIACION NOMINA "
                  + (f"{fechas[-1]:%m-%Y} " if fechas else "")
                  + (empresa.split(" S.A.S")[0].split(" SAS")[0]
                     if empresa else "")).strip() + ".xlsx"
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary",
            key="conc_nom_descargar", use_container_width=True)
    except Exception as error:
        reportar_error("No se pudo armar el Excel de la conciliación", error)


def _flujo_nomina_empresa_a():
    titulo_seccion(
        "Archivos", 1,
        "Carga la <b>base de datos de nómina</b> (Excel), la <b>planilla de "
        "nómina</b> en PDF y <b>todos los PDF de vacaciones</b> que haya (el "
        "general y los que salen por empleado; si una misma liquidación "
        "viene en dos PDF se cuenta una sola vez).")
    c1, c2, c3 = st.columns(3)
    with c1:
        encabezado_carga(
            "XLSX", "Base de datos de nómina", "Obligatorio · .xlsx",
            "Excel de pagos con <b>NUMERO DE IDENTIFICACION</b>, "
            "<b>NOMBRE</b>, <b>APELLIDO</b>, datos bancarios, <b>VALOR DEL "
            "PAGO O DE LA RECARGA</b>, <b>VACACIONES</b> y TOTAL A PAGAR. "
            "Solo se cambian las columnas de valor del pago y vacaciones; "
            "el formato del archivo se conserva.")
        f_base = st.file_uploader("Base de datos", type=["xlsx", "xlsm"],
                                  key="hib_base",
                                  label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "PDF", "Planilla de nómina", "Obligatorio · uno o varios PDF",
            "«Planilla de Nómina» del periodo: de cada empleado se toma el "
            "<b>NETO</b> (recalculado como devengos − deducciones, porque el "
            "PDF recorta los decimales).")
        f_planillas = st.file_uploader(
            "Planilla de nómina", type=["pdf"], key="hib_planillas",
            accept_multiple_files=True, label_visibility="collapsed") or []
    with c3:
        encabezado_carga(
            "VAC", "Vacaciones", "Opcional · cualquier cantidad de PDF",
            "«Informe de Vacaciones» general y/o por empleado: se toma el "
            "<b>VALOR TOTAL</b> de cada liquidación (no el sueldo). Quien "
            "no tenga vacaciones queda en 0.")
        f_vac = st.file_uploader(
            "Vacaciones", type=["pdf"], key="hib_vacaciones",
            accept_multiple_files=True, label_visibility="collapsed") or []
    if not (f_base and f_planillas):
        st.info("Carga la base de datos y la planilla de nómina para "
                "continuar.")
        return
    try:
        base = _leer_base_hib_cache(f_base.getvalue())
    except Exception as error:
        reportar_error("No se pudo leer la base de datos", error)
        return
    planillas, informes = [], []
    f_planillas = _sin_repetidos(f_planillas)
    for f in f_planillas:
        try:
            planillas.append(_leer_planilla_hib_cache(f.getvalue(), f.name))
        except Exception as error:
            reportar_error(f"No se pudo leer «{f.name}» como planilla de "
                           "nómina", error)
    for f in f_vac:
        try:
            informes.append(_leer_vacaciones_hib_cache(f.getvalue(), f.name))
        except Exception as error:
            reportar_error(f"No se pudo leer «{f.name}» como informe de "
                           "vacaciones", error)
    if not planillas:
        return
    _planillas_parecidas(planillas, "total_neto", "periodo")

    titulo_seccion("Documentos leídos", 2,
                   "Revisa el periodo, la cantidad de empleados y los "
                   "totales de cada PDF.")
    for p in planillas:
        per = (f"del {p['periodo'][0]} al {p['periodo'][1]}"
               if p.get("periodo") else "periodo no leído")
        st.success(f"Nómina «{p['archivo']}» · {p.get('nomina') or ''} · "
                   f"{per} · pago {p.get('fecha_pago') or '—'} · "
                   f"{len(p['empleados'])} empleados · neto "
                   f"{formato_cop(p['total_neto'])}")
        for aviso in p["avisos"]:
            st.warning(f"«{p['archivo']}»: {aviso}")
    for inf in informes:
        st.success(f"Vacaciones «{inf['archivo']}» · "
                   f"{len(inf['liquidaciones'])} liquidaciones · "
                   f"{formato_cop(inf['total'])}")
        for aviso in inf["avisos"]:
            st.warning(f"«{inf['archivo']}»: {aviso}")
    for aviso in base.get("avisos") or []:
        st.warning(aviso)
    st.caption(f"Excel: hoja «{base['hoja']}», {len(base['empleados'])} "
               f"empleados · VALOR DEL PAGO = columna {base['col_valor']} · "
               f"VACACIONES = columna {base['col_vacaciones']}.")

    huella = _huella(f_base.getvalue(), *[f.getvalue() for f in f_planillas],
                     *[f.getvalue() for f in f_vac])
    if st.session_state.get("hib_huella") != huella:
        st.session_state["hib_huella"] = huella
        st.session_state["hib_cruce"] = cruzar_nomina_empresa_a(
            base, planillas, informes)
        st.session_state["hib_editor_n"] = \
            st.session_state.get("hib_editor_n", 0) + 1
        st.session_state.pop("hib_archivo", None)
    cruce = st.session_state["hib_cruce"]
    if cruce["liquidaciones_repetidas"]:
        st.info(f"{cruce['liquidaciones_repetidas']} liquidaciones de "
                "vacaciones venían en más de un PDF y se contaron una sola "
                "vez.")

    titulo_seccion(
        "Alertas", 3,
        "Empleados que no están en los dos documentos o cuyo nombre no "
        "coincide con la cédula. El Excel <b>no se modifica</b> para ellos.")
    alertas = alertas_nomina_empresa_a(cruce)
    for texto in alertas:
        st.warning(texto)
    if not alertas:
        st.success("Todos los empleados de los PDF están en el Excel y "
                   "viceversa, con cédula y nombre coincidentes.")

    titulo_seccion(
        "Revisión", 4,
        "Una fila por empleado del Excel, en su mismo orden. Solo se "
        "actualizan las marcadas en <b>Actualizar</b>.")
    import pandas as pd
    tabla = pd.DataFrame([{
        "Fila": f["fila"], "Cédula": f["cedula"],
        "Nombre en el Excel": f["nombre"],
        "Nombre en el PDF": f["nombre_planilla"],
        "Coincidencia": (f"{f['similitud'] * 100:.0f} %"
                         if f["similitud"] is not None else ""),
        "Valor del pago actual": f["valor"],
        "Neto nómina (nuevo)": f["neto"],
        "Vacaciones actual": f["vacaciones"],
        "Vacaciones (nuevo)": f["vac_nueva"],
        "Total a pagar": round((f["neto"] if f["neto"] is not None
                                else (f["valor"] or 0)) + f["vac_nueva"], 2),
        "Estado": ESTADOS_NOMINA.get(f["estado"], f["estado"]).replace(
            "ninguna planilla", "la planilla de nómina"),
        "Actualizar": f.get("actualizar", f["estado"] == "ok"),
    } for f in cruce["filas"]])
    editada = st.data_editor(
        tabla, key=f"hib_editor_{st.session_state['hib_editor_n']}",
        use_container_width=True, hide_index=True, height=480,
        disabled=[c for c in tabla.columns if c != "Actualizar"],
        column_config={
            c: st.column_config.NumberColumn(format="%.2f")
            for c in ("Valor del pago actual", "Neto nómina (nuevo)",
                      "Vacaciones actual", "Vacaciones (nuevo)",
                      "Total a pagar")})
    for f, (_, fila) in zip(cruce["filas"], editada.iterrows()):
        f["actualizar"] = bool(fila["Actualizar"]) and \
            f["estado"] != "repetido" and \
            (f["neto"] is not None or f["vac_nueva"])

    valores, vacaciones = {}, {}
    for f in cruce["filas"]:
        if not f.get("actualizar"):
            continue
        if f["neto"] is not None:
            valores[f["fila"]] = f["neto"]
        vacaciones[f"{base['col_vacaciones']}{f['fila']}"] = f["vac_nueva"]
    total_h = round(sum(valores.get(f["fila"], f["valor"] or 0)
                        for f in cruce["filas"]), 2)
    total_i = round(sum(vacaciones.get(
        f"{base['col_vacaciones']}{f['fila']}", f["vacaciones"] or 0)
        for f in cruce["filas"]), 2)
    dif_h = round(total_h - cruce["total_neto"], 2)
    dif_i = round(total_i - cruce["total_vacaciones"], 2)
    kpis([
        {"etiqueta": "Filas que se actualizan", "valor": str(len(vacaciones)),
         "icono": "capas", "tono": "indigo",
         "detalle": f"de {len(cruce['filas'])} en el Excel"},
        {"etiqueta": "Valor del pago (Excel)", "valor": formato_cop(total_h),
         "icono": "dinero", "tono": "teal",
         "detalle": f"Planilla {formato_cop(cruce['total_neto'])}",
         "estado": "ok" if abs(dif_h) < .005 else "alerta"},
        {"etiqueta": "Vacaciones (Excel)", "valor": formato_cop(total_i),
         "icono": "calendario", "tono": "ambar",
         "detalle": f"PDF {formato_cop(cruce['total_vacaciones'])}",
         "estado": "ok" if abs(dif_i) < .005 else "alerta"},
        {"etiqueta": "Total a pagar", "valor": formato_cop(total_h + total_i),
         "icono": "nomina", "tono": "magenta"}])
    faltan_neto = round(sum(d["neto"] for d in cruce["solo_planilla"]), 2)
    if faltan_neto:
        st.caption(f"La planilla suma {formato_cop(cruce['total_neto'])}; "
                   f"{formato_cop(faltan_neto)} son de empleados que no "
                   "están en el Excel (ver alertas).")

    titulo_seccion(
        "Generar y descargar", 5,
        "Descarga el mismo Excel con <b>solo</b> las columnas VALOR DEL PAGO "
        "O DE LA RECARGA y VACACIONES actualizadas en las filas marcadas. "
        "Formatos, fórmulas (TOTAL A PAGAR y sumas) y demás celdas quedan "
        "igual; las fórmulas se recalculan al abrir.")
    if st.button("Generar base de datos actualizada", type="primary",
                 key="hib_generar", use_container_width=True, disabled=not vacaciones):
        try:
            contenido, _ = actualizar_valores_xlsx(
                f_base.getvalue(), base["hoja"], base["col_valor"], valores,
                vacaciones)
            st.session_state["hib_archivo"] = (f_base.name, contenido)
        except Exception as error:
            reportar_error("No se pudo generar el archivo", error)
    if st.session_state.get("hib_archivo"):
        nombre, contenido = st.session_state["hib_archivo"]
        st.success(f"Listo: {nombre} · {len(valores)} valores del pago y "
                   f"{len(vacaciones)} de vacaciones actualizados.")
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary", key="hib_descargar", use_container_width=True)


def _sin_repetidos(archivos):
    """v6.6: el mismo PDF cargado dos veces (mismo contenido, aunque tenga
    otro nombre) duplicaria los valores a pagar: se usa una sola vez y se
    avisa."""
    vistos, unicos = {}, []
    for f in archivos:
        llave = _huella(f.getvalue())
        if llave in vistos:
            st.warning(f"«{f.name}» es el mismo archivo que "
                       f"«{vistos[llave]}»: se tomó una sola vez para no "
                       "duplicar los valores.")
            continue
        vistos[llave] = f.name
        unicos.append(f)
    return unicos


def _planillas_parecidas(planillas, clave_total, clave_concepto):
    """Avisa si dos planillas distintas traen el mismo concepto, la misma
    cantidad de empleados y el mismo total (¿la misma planilla exportada dos
    veces?). No se descarta ninguna: se suma lo cargado, pero se advierte."""
    firmas = {}
    for p in planillas:
        firma = (p.get(clave_concepto), len(p["empleados"]),
                 round(p.get(clave_total) or 0, 2))
        if firma in firmas:
            st.warning(f"«{p['archivo']}» y «{firmas[firma]}» tienen el mismo "
                       "concepto, los mismos empleados y el mismo total: si "
                       "son la misma planilla, quita una para no pagar "
                       "doble.")
        firmas[firma] = p["archivo"]


def modulo_nomina():
    banner_modulo(
        "Módulo 6 · Nómina",
        "Pagos de nómina",
        "Actualiza el archivo de pagos de la nómina con lo que dicen los PDF "
        "de nómina y vacaciones: busca a cada empleado por cédula y nombre, "
        "suma los conceptos y solo cambia los valores a pagar de las filas "
        "que ya existen, conservando el formato del archivo.",
        ("Planillas en PDF", "Cruce por cédula y nombre",
         "Salida: el mismo Excel, solo con los valores al día"),
    )
    formato_nomina = st.radio(
        "¿Qué vas a hacer?", list(FORMATOS_NOMINA),
        format_func=lambda k: FORMATOS_NOMINA[k], horizontal=True,
        key="nom_tipo_formato",
        help="Formato del banco: se actualiza ValorTransaccion, la "
             "descripción del pago y la fecha de aplicación con las "
             "planillas de pago. Base de datos EMPRESA A: se actualizan el "
             "VALOR DEL PAGO (neto de la planilla de nómina) y las "
             "VACACIONES (valor total de los informes de vacaciones). "
             "Conciliación: compara lo pagado según HELISA con la "
             "liquidación de nómina y con la contabilidad, sin modificar "
             "ningún archivo. Facturación por horas: cuánto facturar cada "
             "mes por los empleados de una BU según los días pagados y la "
             "tarifa por hora.")
    if formato_nomina == "empresa_a":
        _flujo_nomina_empresa_a()
        return
    if formato_nomina == "conciliacion":
        _flujo_conciliacion_nomina()
        return
    if formato_nomina == "electronica":
        _flujo_nomina_electronica()
        return
    if formato_nomina == "facturacion":
        _flujo_facturacion_horas()
        return

    titulo_seccion(
        "Archivos", 1,
        "Carga el <b>formato de pagos del banco</b> (Excel, el mismo que se "
        "sube al portal) y <b>una o varias planillas de pago</b> en PDF. Si "
        "hay planilla de nómina y también de prima, vacaciones u otro "
        "concepto, cárgalas juntas: el valor de cada empleado es la suma de "
        "todas.")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga(
            "BANCO", "Formato de pagos", "Obligatorio · .xlsx",
            "Formato del banco (p. ej. FORMATOPAB · conversor de pagos) con "
            "los beneficiarios: <b>Nit Beneficiario</b>, <b>Nombre "
            "Beneficiario</b> y <b>ValorTransaccion</b>. Solo se cambia esa "
            "columna; nunca se agregan ni se borran empleados.")
        f_excel = st.file_uploader("Formato de pagos", type=["xlsx", "xlsm"],
                                   key="nom_formato",
                                   label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "PDF", "Planillas de pago", "Obligatorio · uno o varios PDF",
            "Planilla de pago (consignación del periodo) con nombre, "
            "identificación y <b>valor</b> de cada empleado. Puedes cargar "
            "varias (nómina, prima, vacaciones…).")
        f_planillas = st.file_uploader(
            "Planillas", type=["pdf"], key="nom_planillas",
            accept_multiple_files=True, label_visibility="collapsed") or []
    if not (f_excel and f_planillas):
        st.info("Carga el formato de pagos y al menos una planilla para "
                "continuar.")
        return

    try:
        formato = _leer_formato_pagos_cache(f_excel.getvalue())
    except Exception as error:
        reportar_error("No se pudo leer el formato de pagos", error)
        return
    planillas = []
    f_planillas = _sin_repetidos(f_planillas)
    for f in f_planillas:
        try:
            planillas.append(_leer_planilla_nomina_cache(f.getvalue(), f.name))
        except Exception as error:
            reportar_error(f"No se pudo leer «{f.name}»", error)
    if not planillas:
        return
    _planillas_parecidas(planillas, "total", "concepto")

    titulo_seccion(
        "Planillas leídas", 2,
        "Revisa que cada planilla tenga todos sus empleados y que la suma "
        "coincida con su TOTAL.")
    for p in planillas:
        st.success(f"«{p['archivo']}» · {p['concepto']} · "
                   f"{len(p['empleados'])} empleados · total "
                   f"{formato_cop(p['total'])}")
        for aviso in p["avisos"]:
            st.warning(f"«{p['archivo']}»: {aviso}")
    st.caption(f"Excel: hoja «{formato['hoja']}», "
               f"{len(formato['empleados'])} empleados (filas "
               f"{formato['fila_titulos'] + 1} a "
               f"{formato['fila_titulos'] + len(formato['empleados'])}), "
               f"columna {formato['columna_valor']} = ValorTransaccion.")

    titulo_seccion(
        "Periodo de pago", 3,
        "La <b>quincena</b> y el <b>mes</b> arman la descripción del pago del "
        "lote (NOM + 1ERAQ / 2DAQ + mes, p. ej. <b>NOM2DAQOCT</b>) y la "
        "<b>fecha de pago</b> va en «Fecha de aplicación» de todos los "
        "empleados (formato AAAAMMDD, p. ej. 20261030). Se proponen según el "
        "periodo de la planilla.")
    periodo = periodo_de_planillas(planillas)
    fin = periodo[1] if periodo else datetime.date.today()
    c1, c2, c3 = st.columns(3)
    with c1:
        quincena = st.selectbox(
            "Quincena", [1, 2], index=0 if fin.day <= 15 else 1,
            format_func=lambda q: "1ª quincena (1ERAQ)" if q == 1
            else "2ª quincena (2DAQ)", key="nom_quincena")
    with c2:
        mes = st.selectbox(
            "Mes", list(range(1, 13)), index=fin.month - 1,
            format_func=lambda m: f"{MESES_NOMINA_NOMBRE[m - 1]} "
                                  f"({MESES_NOMINA[m - 1]})", key="nom_mes")
    with c3:
        fecha_pago = st.date_input("Fecha de pago (Fecha de aplicación)",
                                   value=fin, key="nom_fecha_pago",
                                   format="DD/MM/YYYY")
    codigo = codigo_descripcion_nomina(quincena, mes)
    desc = formato.get("descripcion")
    st.caption(
        f"Descripción del pago: {codigo}"
        + (f" (celda {desc['celda']}; hoy dice «{desc['valor']}»)" if desc
           else "")
        + f" · Fecha de aplicación: {fecha_aplicacion_numero(fecha_pago)}"
        + (f" (columna {formato['columna_fecha']}; hoy dice "
           f"{formato.get('fecha_actual')})" if formato.get("columna_fecha")
           else ""))
    if not desc:
        st.warning("No se encontró la celda «DESCRIPCIÓN DEL PAGO» en el "
                   "Excel: la descripción no se actualizará.")
    if not formato.get("columna_fecha"):
        st.warning("No se encontró la columna «Fecha de aplicación» en el "
                   "Excel: la fecha no se actualizará.")

    huella = _huella(f_excel.getvalue(), *[f.getvalue() for f in f_planillas])
    if st.session_state.get("nom_huella") != huella:
        st.session_state["nom_huella"] = huella
        st.session_state["nom_cruce"] = cruzar_nomina(formato, planillas)
        st.session_state["nom_editor_n"] = \
            st.session_state.get("nom_editor_n", 0) + 1
        st.session_state.pop("nom_archivo", None)
    cruce = st.session_state["nom_cruce"]

    titulo_seccion(
        "Alertas", 4,
        "Empleados que no están en los dos documentos o cuyo nombre no "
        "coincide con la cédula. El Excel <b>no se modifica</b> para ellos: "
        "si hay que agregar o quitar a alguien, hazlo en el formato del "
        "banco.")
    alertas = alertas_nomina(cruce)
    if alertas:
        for texto, _ in alertas:
            st.warning(texto)
    else:
        st.success("Todos los empleados están en el Excel y en las planillas, "
                   "con cédula y nombre coincidentes.")

    titulo_seccion(
        "Revisión", 5,
        "Una fila por empleado del Excel, en su mismo orden. Solo se "
        "actualizan las marcadas en <b>Actualizar</b>.")
    _glosario_pp(GLOSARIO_NOMINA)
    import pandas as pd
    tabla = pd.DataFrame([{
        "Fila": f["fila"], "Cédula": f["cedula"],
        "Nombre en el Excel": f["nombre"],
        "Nombre en la planilla": f["nombre_planilla"],
        "Coincidencia": (f"{f['similitud'] * 100:.0f} %"
                         if f["similitud"] is not None else ""),
        "Conceptos": " + ".join(f"{c}: {formato_cop(v)}"
                                for c, v in f["detalle"]),
        "Valor actual": f["valor"],
        "Valor planillas": f["valor_nuevo"],
        "Estado": ESTADOS_NOMINA.get(f["estado"], f["estado"]),
        "Actualizar": f.get("actualizar", f["estado"] == "ok"),
        "Nota": f["nota"],
    } for f in cruce["filas"]])
    ayudas = {k: re.sub(r"<[^>]+>", "", v) for k, v in GLOSARIO_NOMINA}
    editada = st.data_editor(
        tabla, key=f"nom_editor_{st.session_state['nom_editor_n']}",
        use_container_width=True, hide_index=True, height=480,
        disabled=[c for c in tabla.columns if c != "Actualizar"],
        column_config={
            "Valor actual": st.column_config.NumberColumn(
                format="%.2f", help=ayudas["Valor actual"]),
            "Valor planillas": st.column_config.NumberColumn(
                format="%.2f", help=ayudas["Valor planillas"]),
            "Coincidencia": st.column_config.TextColumn(
                help=ayudas["Coincidencia"]),
            "Actualizar": st.column_config.CheckboxColumn(
                help=ayudas["Actualizar"]),
            "Nota": st.column_config.TextColumn(width="large"),
        })
    for f, (_, fila) in zip(cruce["filas"], editada.iterrows()):
        f["actualizar"] = bool(fila["Actualizar"]) and \
            f["valor_nuevo"] is not None and f["estado"] != "repetido"

    valores = {f["fila"]: f["valor_nuevo"] for f in cruce["filas"]
               if f.get("actualizar")}
    total_planillas = round(sum(p["total"] for p in planillas), 2)
    total_excel = round(sum(
        (valores.get(f["fila"], f["valor"]) or 0) for f in cruce["filas"]), 2)
    dif = round(total_excel - total_planillas, 2)
    kpis([
        {"etiqueta": "Filas que se actualizan", "valor": str(len(valores)),
         "icono": "capas", "tono": "indigo",
         "detalle": f"de {len(cruce['filas'])} en el Excel"},
        {"etiqueta": "Total planillas", "valor": formato_cop(total_planillas),
         "icono": "documentos", "tono": "teal"},
        {"etiqueta": "Total del Excel después", "valor": formato_cop(
            total_excel), "icono": "archivo", "tono": "magenta"},
        {"etiqueta": "Diferencia", "valor": formato_cop(dif), "icono": "balanza",
         "tono": "verde" if abs(dif) < .005 else "ambar",
         "estado": "ok" if abs(dif) < .005 else "alerta"}])
    # v6.14: composicion de la diferencia Excel vs planillas (solo alerta:
    # nunca se agregan ni se borran empleados).
    mostrar_diferencias(panel_nomina_banco(cruce, planillas, valores),
                        "nom_dif")
    sin = [f for f in cruce["filas"] if f["estado"] == "sin_planilla"]
    if sin:
        st.caption("Los empleados del Excel que no están en ninguna planilla "
                   "conservan su valor actual ("
                   + formato_cop(sum(f["valor"] or 0 for f in sin))
                   + "): por eso el total del Excel puede no cuadrar con las "
                     "planillas.")

    titulo_seccion(
        "Generar y descargar", 6,
        "Descarga el mismo Excel del banco con <b>solo</b> la columna "
        "ValorTransaccion actualizada en las filas marcadas, la descripción "
        "del pago del lote y la fecha de aplicación de todos los empleados. "
        "Todo lo demás "
        "(otras columnas, hojas, listas y validaciones) queda igual. Las "
        "sumas del Excel se recalculan al abrirlo.")
    if st.button("Generar formato actualizado", type="primary",
                 key="nom_generar", use_container_width=True, disabled=not valores):
        try:
            otras = {}
            if desc:
                otras[desc["celda"]] = codigo
            if formato.get("columna_fecha"):
                for e in formato["empleados"]:
                    otras[f"{formato['columna_fecha']}{e['fila']}"] = \
                        fecha_aplicacion_numero(fecha_pago)
            contenido, n = actualizar_valores_xlsx(
                f_excel.getvalue(), formato["hoja"], formato["columna_valor"],
                valores, otras)
            n = len(valores)
            st.session_state["nom_archivo"] = (
                f_excel.name, contenido, n, codigo, fecha_pago)
        except Exception as error:
            reportar_error("No se pudo generar el archivo", error)
    archivo = st.session_state.get("nom_archivo")
    if archivo and archivo[3:] != (codigo, fecha_pago):
        st.session_state.pop("nom_archivo", None)   # cambio el periodo
        archivo = None
    if archivo:
        nombre, contenido, n = archivo[:3]
        st.success(f"Listo: {nombre} · {n} valores actualizados · "
                   f"descripción {codigo} · fecha de aplicación "
                   f"{fecha_aplicacion_numero(fecha_pago)}.")
        st.download_button(
            "Descargar " + nombre, contenido, file_name=nombre,
            mime="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet", type="primary", key="nom_descargar", use_container_width=True)


# ============================================================
# v6.21 · Facturacion por horas EMPRESA A
# ============================================================
@_cache
def _leer_costos_fac(contenido):
    return FAC.leer_costos_nomina(contenido)


@_cache
def _leer_tarifas_fac(contenido):
    return FAC.leer_tarifas(contenido)


def _flujo_facturacion_horas():
    import pandas as pd
    titulo_seccion(
        "Archivos", 1,
        "El libro de <b>nómina y costos</b> trae, por mes, la BU de cada "
        "empleado y los <b>días pagados en el mes (PILA)</b>; la hoja "
        "<b>INGRESOS Y RETIROS</b> completa los días que falten. El "
        "<b>Resumen Tarifas</b> trae la tarifa mínima y máxima por hora (USD) "
        "de cada colaborador (hoja «Tarifa Colaborador»).")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga(
            "XLSX", "Nómina y costos", "Obligatorio · .xlsx",
            "NOMINA Y COSTOS COLOMBIA … CON INGRESOS Y RETIROS: hojas «Nomina "
            "<mes>» con BU, NIT o (Id.) y DÍAS PAGADOS EN ESTE MES (PILA).")
        f_costos = st.file_uploader("Nómina y costos", type=["xlsx", "xlsm"],
                                    key="fac_costos",
                                    label_visibility="collapsed")
    with c2:
        encabezado_carga(
            "XLSX", "Resumen de tarifas", "Obligatorio · .xlsx",
            "Tabla Identificación, Nombre, Cargo, Min y Max (USD por hora).")
        f_tarifas = st.file_uploader("Tarifas", type=["xlsx", "xlsm"],
                                     key="fac_tarifas",
                                     label_visibility="collapsed")
    if not (f_costos and f_tarifas):
        st.info("Carga el libro de nómina y costos y el resumen de tarifas "
                "para continuar.")
        return
    try:
        with st.spinner("Leyendo la nómina y las tarifas…"):
            costos = _leer_costos_fac(f_costos.getvalue())
            tarifas = _leer_tarifas_fac(f_tarifas.getvalue())
    except Exception as error:
        reportar_error("No se pudieron leer los archivos", error)
        return
    for a in costos["avisos"] + tarifas["avisos"]:
        st.warning(a)

    titulo_seccion(
        "Parámetros", 2,
        "Por defecto: solo la BU <b>BU1</b>, <b>tarifa mínima</b> y horas "
        "en <b>proporción de 30 días = 168 h</b> (la PILA paga 30 días el mes "
        "completo). Todo se puede cambiar aquí y también después en la hoja "
        "PARAMETROS del Excel.")
    cfg = dict(FAC.CONFIG_FACTURACION)
    # v6.23: cargos por cedula guardados (dato privado, fuera del codigo).
    guardados = {str(k): v for k, v in
                 (leer_privado(ARCHIVO_CARGOS_FAC, {}) or {}).items() if v}
    cfg["cargos"] = dict(guardados)
    c1, c2, c3 = st.columns(3)
    opciones_bu = sorted(costos["bus"])
    cfg["bus"] = c1.multiselect(
        "BU a facturar", opciones_bu,
        default=[b for b in cfg["bus"] if b in opciones_bu],
        key="fac_bus")
    cfg["factor"] = c2.slider(
        "Tarifa: 0 = mínima, 1 = máxima", 0.0, 1.0, 0.0, 0.05,
        key="fac_factor")
    cfg["metodo"] = c3.radio(
        "Horas del mes", list(FAC.METODOS),
        format_func=lambda k: FAC.METODOS[k], key="fac_metodo",
        help="Proporción: días ÷ 30 × 168. Semanas: días ÷ 5 × 42. En los "
             "dos, hora completa (0,5 sube) y tope de 168.")
    with st.expander("Horas por semana, semanas y cargos sin tarifa"):
        c1, c2, c3, c4 = st.columns(4)
        cfg["horas_semana"] = c1.number_input("Horas por semana", 1, 60, 42,
                                              key="fac_hs")
        cfg["semanas_mes"] = c2.number_input("Semanas por mes", 1, 5, 4,
                                             key="fac_sm")
        cfg["dias_semana"] = c3.number_input("Días por semana", 1, 7, 5,
                                             key="fac_ds")
        cfg["dias_mes"] = c4.number_input("Días del mes (PILA)", 28, 31, 30,
                                          key="fac_dm")
        cargos = [t[0] for t in tarifas["cargos"].values()]
        # Empleados de las BU elegidas sin tarifa en la lista.
        sin_lista = OrderedDict()
        for filas in costos["meses"].values():
            for f in filas:
                if FAC.clave(f["bu"]) in {FAC.clave(b) for b in cfg["bus"]} \
                        and f["cedula"] and f["cedula"] not in \
                        tarifas["por_cedula"] and (f["dias"] or 0) > 0:
                    sin_lista.setdefault(f["cedula"], f["nombre"])
        if sin_lista:
            st.caption("Empleados que no están en la lista de tarifas: toman "
                       "la tarifa del cargo de su contrato.")
            tabla = pd.DataFrame([{
                "Identificación": c, "Empleado": n,
                "Cargo (contrato)": cfg["cargos"].get(c, "")}
                for c, n in sin_lista.items()])
            editada = st.data_editor(
                tabla, hide_index=True, use_container_width=True,
                key="fac_cargos", column_config={
                    "Identificación": st.column_config.TextColumn(
                        disabled=True),
                    "Empleado": st.column_config.TextColumn(disabled=True),
                    "Cargo (contrato)": st.column_config.SelectboxColumn(
                        options=[""] + cargos)})
            elegidos = {str(r["Identificación"]): r["Cargo (contrato)"]
                        for _, r in editada.iterrows()}
            cfg["cargos"] = {**guardados, **elegidos}
            nuevos = {**guardados, **{k: v for k, v in elegidos.items() if v}}
            if nuevos != guardados and st.button(
                    "Guardar cargos para las próximas veces",
                    key="fac_cargos_guardar"):
                try:
                    donde = guardar_privado(ARCHIVO_CARGOS_FAC, nuevos)
                    st.success(f"Cargos guardados en {donde}.")
                except Exception as error:
                    reportar_error("No se pudieron guardar los cargos", error)
    if not cfg["bus"]:
        st.info("Elige al menos una BU.")
        return
    r = FAC.armar_facturacion(costos, tarifas, cfg)

    titulo_seccion("Resultado", 3,
                   "Valor por empleado = horas × tarifa aplicada, a centavos. "
                   "Los meses sin nadie de la BU no se facturan.")
    con = [m for m in r["meses"] if m["filas"]]
    sin = sum(len(m["filas"]) - sum(1 for x in m["filas"]
                                    if x["valor"] is not None)
              for m in r["meses"])
    kpis([
        {"etiqueta": "Valor a facturar (USD)",
         "valor": f"US$ {r['totales']['valor']:,.2f}".replace(",", "X")
         .replace(".", ",").replace("X", "."), "icono": "dinero",
         "tono": "magenta",
         "detalle": f"{con[0]['nombre']} a {con[-1]['nombre']}" if con
         else ""},
        {"etiqueta": "Horas", "valor": f"{r['totales']['horas']:,}"
         .replace(",", "."), "icono": "reloj", "tono": "indigo"},
        {"etiqueta": "Meses", "valor": str(len(con)), "icono": "calendario",
         "tono": "teal"},
        {"etiqueta": "Líneas sin tarifa", "valor": str(sin), "icono":
         "alerta", "tono": "ambar" if sin else "verde",
         "estado": "alerta" if sin else "ok",
         "estado_texto": "Completar" if sin else "Completo"}])
    if sin:
        st.warning("Hay empleados sin tarifa (naranja en el Excel): asígnales "
                   "el cargo en «Horas por semana, semanas y cargos sin "
                   "tarifa» o completa su tarifa en la hoja TARIFAS.")
    grafico("Valor a facturar por mes (USD)", html_barras(
        [(m["nombre"], m["valor"]) for m in con], " USD"),
        icono_nombre="calendario")
    mes = st.selectbox("Ver el detalle del mes", [m["nombre"] for m in con],
                       key="fac_mes") if con else None
    if mes:
        m = next(x for x in con if x["nombre"] == mes)
        st.dataframe([{"BU": x["bu"], "Nombre empleado": x["nombre"],
                       "Días pagados": x["dias"], "Horas": x["horas"],
                       "Tarifa USD": None if x["tarifa"] is None
                       else round(x["tarifa"], 4),
                       "Valor USD": x["valor"], "Identificación": x["cedula"],
                       "Observación": x["nota"]} for x in m["filas"]],
                     use_container_width=True, hide_index=True)
    if r["observaciones"]:
        with st.expander(f"Observaciones ({len(r['observaciones'])})"):
            st.dataframe([{"Mes": o[0], "Empleado": o[1],
                           "Identificación": o[2], "Observación": o[3]}
                          for o in r["observaciones"]],
                         use_container_width=True, hide_index=True)

    titulo_seccion("Descargar", 4,
                   "Excel con RESUMEN, PARAMETROS (factor, método de horas), "
                   "TARIFAS (editables), una hoja por mes y OBSERVACIONES. "
                   "Las fórmulas quedan vivas: si se cambia el factor o una "
                   "tarifa en el Excel, todo se recalcula.")
    try:
        datos = FAC.excel_facturacion(r)
    except Exception as error:
        reportar_error("No se pudo armar el Excel", error)
        return
    st.download_button(
        "Descargar facturación por horas", datos,
        file_name=FAC.nombre_archivo(r),
        mime="application/vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet", type="primary",
        use_container_width=True, key="fac_descargar")
