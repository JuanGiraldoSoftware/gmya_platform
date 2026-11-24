"""Pantalla "Conciliacion DIAN" (Streamlit). Contrato: modulo_dian().

Depende de: gmya.comun.numeros, gmya.comun.cache, gmya.comun.config_equipo, gmya.ui.componentes, gmya.ui.visor, gmya.modulos.dian.parametros, gmya.modulos.dian.lectura, gmya.modulos.dian.acuses, gmya.modulos.dian.analisis, gmya.modulos.dian.excel, gmya.modulos.dian.simplificado, gmya.modulos.dian.visor, gmya.ui.interfaz_comun, gmya.registro.interfaz
"""

import copy
import html
from collections import Counter
from decimal import Decimal

import streamlit as st

from gmya.comun.numeros import formato_cop
from gmya.comun.cache import _cache
from gmya.comun.config_equipo import guardar_config, leer_config
from gmya.ui.componentes import (
    ayuda, banner_modulo, encabezado_carga, titulo_seccion,
)
from gmya.ui.visor import contenido_tabla_visor
from gmya.ui.visual import grafico, html_comparativo, kpis, panel_resumen
from gmya.ui.diferencias import mostrar_diferencias
from gmya.modulos.dian.diferencias import (
    conteo_documentos, panel_diferencias_dian,
)
from gmya.modulos.dian.parametros import dato, PARAMETROS_DIAN_BASE
from gmya.modulos.dian.lectura import (
    etiqueta_periodo, leer_varios_reportes_dian, periodo_dian,
)
from gmya.modulos.dian.acuses import (
    eventos_de_reporte, prefijos_eventos, sugerir_prefijos_acuse,
)
from gmya.modulos.dian.analisis import (
    CLAVE_COMBINADO, observacion_documento, resumen_informe_combinado,
)
from gmya.modulos.dian.excel import estado_concepto, partidas_para_revisar
from gmya.modulos.dian.simplificado import generar_conciliacion_dian
from gmya.modulos.dian.visor import (
    diferencias_dian, marcas_dian, tabla_informe_helisa, tabla_reporte_dian,
)
from gmya.ui.interfaz_comun import _filtro_visor, _mostrar_visor
from gmya.registro.interfaz import reportar_error


# ============================================================
# INTERFAZ: CONCILIACION DIAN
# ============================================================
_AYUDA_INFORMES = (
    " <br><br>Sirve cualquiera de los dos informes de HELISA, tal como se "
    "exportan (<b>PDF</b> o Excel 97-2003, .xls normal o XML): "
    "<b>Comprobante de diario - Resumen</b> (compara "
    "totales por cuenta) o <b>Comprobante diario - Detalle</b>, como las "
    "<b>RELACION ...</b> (cruza documento por documento). El sistema "
    "reconoce cuál es. <b>Opcional</b>: si no lo cargas, el concepto no se "
    "concilia.")

MODO_HELISA_UNO = "Un solo archivo con todos los documentos"
MODO_HELISA_VARIOS = "Un archivo por concepto (FV, NCV, NDV, DSE, NADSE, NC, FC)"
NOMBRE_CONCEPTO_CORTO = {"FV": "Facturas de venta",
                         "NCV": "Notas crédito ventas",
                         "NDV": "Notas débito ventas",
                         "DSE": "Documentos soporte",
                         "NADSE": "Notas ajuste DSE",
                         "NC": "Notas crédito proveedores",
                         "FC": "Facturas de compra"}


@_cache
def _leer_reportes_dian_cache(archivos):
    # Antes se volvia a leer el reporte DIAN en cada clic de la pagina.
    return leer_varios_reportes_dian(list(archivos))


@_cache
def _resumen_combinado_cache(contenido, nombre):
    return resumen_informe_combinado(contenido, nombre)


CARGAS_HELISA = [
    {
        "clave": "FV",
        "titulo": "Facturas electrónicas de venta",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle o Resumen · FEV",
        "ayuda": "Documento <b>FEV - FACTURA ELECTRONICA DE VENTA</b>. Se "
                 "compara el total y el IVA generado (cuenta 2408) contra "
                 "las facturas <b>emitidas</b> en el reporte DIAN. Si HELISA "
                 "incluye un <b>descuento comercial</b> (530535) en el total "
                 "del documento y la DIAN trae la factura neta, se resta "
                 "solo." + _AYUDA_INFORMES,
    },
    {
        "clave": "NCV",
        "titulo": "Notas crédito de ventas",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle o Resumen · NCV",
        "ayuda": "Documento <b>NCV - NOTA CREDITO VENTAS</b>. Se compara "
                 "con las <b>Notas de crédito electrónicas emitidas</b> a "
                 "los clientes en el reporte DIAN (total e IVA, cuenta 2408 "
                 "al débito)." + _AYUDA_INFORMES,
    },
    {
        "clave": "NDV",
        "titulo": "Notas débito de ventas",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle o Resumen · NDV",
        "ayuda": "Documento <b>NDV - NOTA DEBITO VENTAS</b>. Se compara con "
                 "las <b>Notas de débito electrónicas emitidas</b> a los "
                 "clientes en el reporte DIAN (total e IVA, cuenta 2408)."
                 + _AYUDA_INFORMES,
    },
    {
        "clave": "DSE",
        "titulo": "Documentos soporte",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle o Resumen · "
                   "DSE / DSEC",
        "ayuda": "Documento <b>DSE - DOCUMENTO SOPORTE ELECTRONICO</b> (o "
                 "<b>DSEC - DOC SOPORTE ELECTRONICO COMPRA</b>). Se "
                 "compara contra los <b>Documentos soporte con no "
                 "obligados</b> emitidos. Con el Resumen, el <b>AJUSTE AL "
                 "PESO</b> de HELISA se resta antes de comparar. Los "
                 "<b>impuestos asumidos</b> (cuenta 5315) solo se toman si "
                 "al restarlos el documento o el total cuadra con la DIAN, "
                 "y el IVA del sistema sale de las cuentas 2408 (p. ej. "
                 "24080212) cuando coincide con el IVA DIAN."
                 + _AYUDA_INFORMES,
    },
    {
        "clave": "NADSE",
        "titulo": "Notas de ajuste de documento soporte",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle o Resumen · "
                   "NADSE",
        "ayuda": "Documento <b>NADSE - NOTA DE AJUSTE DOCUMENTO "
                 "SOPORTE</b>. Se compara con las <b>Notas de ajuste del "
                 "documento soporte</b> emitidas en el reporte DIAN."
                 + _AYUDA_INFORMES,
    },
    {
        "clave": "NC",
        "titulo": "Notas crédito de proveedores",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle o Resumen · NDC",
        "ayuda": "Documento <b>NDC - NOTA DEBITO COMPRAS</b>. Se compara "
                 "con las <b>Notas de crédito electrónicas recibidas</b> de "
                 "los proveedores en el reporte DIAN." + _AYUDA_INFORMES,
    },
    {
        "clave": "FC",
        "titulo": "Facturas de compra",
        "informe": "Opcional · PDF o Excel de HELISA · Detalle · FC / FCC",
        "ayuda": "Documento <b>FC - FACTURA DE COMPRA</b> (o <b>FCC - "
                 "FACTURA DE COMPRA POR MODULO</b>). El cruce es "
                 "<b>factura por factura</b> (NIT del proveedor + prefijo y "
                 "folio) contra las facturas y documentos equivalentes (POS) "
                 "<b>recibidos</b> en la DIAN, marcando IVA (y la diferencia "
                 "de IVA por documento), impuesto al consumo, facturas NO "
                 "DIAN, redondeos, folios mal digitados y gastos no "
                 "deducibles. Las notas NDC que vengan en este informe se "
                 "identifican como de NC." + _AYUDA_INFORMES,
    },
]


def invalidar_dian():
    st.session_state.pop("dian_resultado_gmya", None)


def _lista(texto):
    return [p.strip() for p in str(texto or "").split(",") if p.strip()]


def _cop(valor):
    if valor is None:
        return "—"
    return formato_cop(Decimal(str(round(valor, 2))))


def parametros_dian_ui(reporte):
    """Construye los parametros desde los controles de la interfaz."""
    parametros = copy.deepcopy(PARAMETROS_DIAN_BASE)

    with st.expander("Parámetros de la conciliación DIAN", expanded=False):
        st.caption(
            "Los valores por defecto reproducen la conciliación manual de "
            "la firma. Ajústalos solo si el cliente maneja otras cuentas o "
            "consecutivos.")

        c1, c2, c3 = st.columns(3)
        parametros["tolerancia_redondeo"] = c1.number_input(
            "Tolerancia de redondeo por factura (COP)",
            min_value=0.0, max_value=100000.0,
            value=float(PARAMETROS_DIAN_BASE["tolerancia_redondeo"]),
            step=10.0, key="dian_tol_redondeo",
            help="Por defecto 0: la factura debe ser exacta, centavos "
                 "incluidos. Si se sube, una diferencia menor o igual se "
                 "marca como REDONDEO y se lleva a la columna NO DIAN; por "
                 "encima se reporta como DIFERENCIA DE VALOR.")
        parametros["tolerancia_estado"] = c2.number_input(
            "Diferencia máxima para marcar CONCILIADO (COP)",
            min_value=0.0, max_value=100000.0,
            value=float(PARAMETROS_DIAN_BASE["tolerancia_estado"]),
            step=1.0, key="dian_tol_estado",
            help="Por defecto 0: un concepto solo queda CONCILIADO si la "
                 "diferencia del total y del IVA es exactamente 0.")
        parametros["tolerancia_folio"] = c3.number_input(
            "Tolerancia del cruce por valor (COP)",
            min_value=0.0, max_value=1000.0,
            value=float(PARAMETROS_DIAN_BASE["tolerancia_folio"]),
            step=0.5, key="dian_tol_folio",
            help="Si el número del documento no coincide (folio mal "
                 "digitado en HELISA), se cruza por NIT y valor. Por defecto "
                 "0: el valor debe ser exacto. Queda marcado como FOLIO "
                 "DISTINTO.")

        st.markdown(
            "**Acuses (eventos) de facturas a crédito**"
            + ayuda("<b>Cómo se determinan.</b> El reporte DIAN no dice a "
                    "qué factura corresponde cada evento (Application "
                    "response): se cruza por <b>proveedor</b> (NIT Receptor "
                    "del evento = NIT Emisor de la factura) y por el "
                    "<b>prefijo del folio</b> del evento, que indica la "
                    "clase de acuse. Un evento solo sirve para una factura "
                    "del mismo día o anterior y se usa una sola vez. Si "
                    "ACUSE 1 y 2 tienen el mismo prefijo (un solo "
                    "consecutivo), cada factura toma dos eventos seguidos. "
                    "Si el acuse se dio después de descargar el reporte, "
                    "carga un reporte posterior en <b>Eventos "
                    "posteriores</b>. La hoja <b>ACUSES</b> del Excel "
                    "muestra el evento tomado para cada factura y por qué "
                    "quedó en NO.", "claro"),
            unsafe_allow_html=True)
        conteo = dict(prefijos_eventos(reporte)) if reporte else {}
        prefijos = list(conteo)
        sugeridos = sugerir_prefijos_acuse(reporte) if reporte \
            else [None, None]
        opciones = ["(ninguno)"] + prefijos

        def indice(n):
            p = sugeridos[n - 1]
            return opciones.index(p) if p in opciones else 0

        c1, c2, c3 = st.columns(3)
        etiquetas = {p: f"{p} ({conteo.get(p, 0)} eventos)"
                     for p in prefijos}
        # La llave depende de los prefijos detectados: al cargar otro
        # reporte los selectores vuelven a la sugerencia automatica.
        sufijo = "_".join(prefijos + [str(p) for p in sugeridos]) or "sin"
        a1 = c1.selectbox("ACUSE 1 · prefijo del folio", opciones,
                          index=indice(1), key=f"dian_acuse1_{sufijo}",
                          format_func=lambda p: etiquetas.get(p, p),
                          help="Prefijo de los 'Application response' "
                               "emitidos por la empresa para el acuse de "
                               "recibo de la factura. Sugerido: el prefijo "
                               "que se emite primero para cada factura.")
        a2 = c2.selectbox("ACUSE 2 · prefijo del folio", opciones,
                          index=indice(2), key=f"dian_acuse2_{sufijo}",
                          format_func=lambda p: etiquetas.get(p, p),
                          help="Prefijo de los eventos de recibo del bien "
                               "o prestación del servicio. Puede ser el "
                               "mismo de ACUSE 1 si la empresa usa un solo "
                               "consecutivo para todos los eventos.")
        a3 = c3.selectbox("ACUSE 3 · prefijo del folio", opciones,
                          index=0, key=f"dian_acuse3_{sufijo}",
                          format_func=lambda p: etiquetas.get(p, p),
                          help="Opcional: aceptación expresa. Si queda en "
                               "(ninguno) la columna ACUSE 3 queda vacía "
                               "para las facturas a crédito.")
        # "" = sin acuse (None queda reservado para deteccion automatica).
        parametros["prefijo_acuse_1"] = "" if a1 == "(ninguno)" else a1
        parametros["prefijo_acuse_2"] = "" if a2 == "(ninguno)" else a2
        parametros["prefijo_acuse_3"] = "" if a3 == "(ninguno)" else a3

        st.markdown("**Cuentas del detalle de compras (FC)**")
        c1, c2, c3 = st.columns(3)
        parametros["palabras_iva"] = _lista(c1.text_input(
            "Cuentas de IVA", ", ".join(PARAMETROS_DIAN_BASE["palabras_iva"]),
            key="dian_iva",
            help="Nombres de cuenta que EMPIEZAN por estas palabras o "
                 "códigos que empiezan por estos números. Su débito se "
                 "lleva a la columna IVA."))
        parametros["palabras_consumo"] = _lista(c2.text_input(
            "Impuesto al consumo",
            ", ".join(PARAMETROS_DIAN_BASE["palabras_consumo"]),
            key="dian_consumo",
            help="Cuentas cuyo débito va a la columna INP. CONSUMO."))
        parametros["palabras_no_deducible"] = _lista(c3.text_input(
            "Gasto no deducible",
            ", ".join(PARAMETROS_DIAN_BASE["palabras_no_deducible"]),
            key="dian_no_ded",
            help="Documentos con una cuenta que contenga estas palabras se "
                 "resaltan en amarillo con la observación GASTO NO "
                 "DEDUCIBLE."))

        st.markdown("**Conceptos y tipos de documento DIAN**")
        tipos_reporte = sorted({
            str(dato(reporte, r, "Tipo de documento"))
            for r in reporte["registros"]}) if reporte else []
        for concepto in parametros["conceptos"]:
            c1, c2, c3 = st.columns([1.1, 2.2, 1.7])
            c1.markdown(
                f"<div class='gm-carga' style='border-radius:12px;"
                f"margin-top:1.75rem'><span class='gm-cod'>"
                f"{concepto['clave']}</span>{concepto['grupo']}</div>",
                unsafe_allow_html=True)
            disponibles = sorted(set(tipos_reporte) | set(concepto["tipos"]))
            concepto["tipos"] = c2.multiselect(
                f"Tipos DIAN para {concepto['clave']}", disponibles,
                default=[t for t in concepto["tipos"] if t in disponibles],
                key=f"dian_tipos_{concepto['clave']}",
                help=f"Documentos del grupo {concepto['grupo']} del reporte "
                     f"DIAN que se comparan con HELISA.")
            texto = c3.text_input(
                f"Ajustes HELISA a restar ({concepto['clave']})",
                ", ".join(concepto["ajustes"]),
                key=f"dian_ajustes_{concepto['clave']}",
                help="Solo aplica si cargas el informe <b>Resumen</b>: "
                     "cuentas que se restan del total HELISA antes de "
                     "comparar (por nombre o código). Ej.: AJUSTE AL PESO. "
                     "Con el informe <b>Detalle</b> (RELACION) el cruce es "
                     "documento por documento y los ajustes salen solos.")
            concepto["ajustes"] = _lista(texto)

    return parametros


def _graficos_conceptos(resultados):
    """v6.16: DIAN vs HELISA conciliado por concepto (total o IVA)."""
    c1, c2 = st.columns([3, 1])
    with c2:
        ver = st.radio("Comparar", ["Total", "IVA"], horizontal=True,
                       key="dian_cmp_ver", label_visibility="collapsed")
        solo = st.toggle("Solo con diferencia", key="dian_cmp_solo")
    filas = []
    for r in resultados:
        if ver == "IVA":
            if r.get("diferencia_iva") is None:
                continue
            a = round(r.get("iva_dian") or 0, 2)
            b = round(a - r["diferencia_iva"], 2)
        else:
            a = round(r["total_dian"], 2)
            b = round(a - r["diferencia_total"], 2)
        if solo and abs(a - b) < 0.005:
            continue
        filas.append((f"{r['concepto']['clave']} · {r['concepto']['nombre']}",
                      a, b))
    with c1:
        grafico(f"{ver} por concepto: DIAN vs HELISA conciliado",
                html_comparativo(filas, "DIAN", "HELISA conciliado",
                                 color_a="#8B95F5", color_b="#E0118F",
                                 pie_diferencia="Diferencia")
                if filas else '<div class="gm-graf-vacio">Todos los '
                'conceptos cuadran.</div>', icono_nombre="balanza")


def mostrar_resultado_dian(resultado):
    analisis = resultado["analisis"]
    resultados = analisis["resultados"]

    titulo_seccion(
        "Resultado de la conciliación DIAN", 4,
        "Para cada concepto: <b>TOTAL DIAN</b> (suma de la columna Total "
        "del reporte), <b>TOTAL HELISA</b> (TOTAL GENERAL del comprobante) "
        "y <b>HELISA conciliado</b> (después de restar ajustes al peso, "
        "facturas NO DIAN y redondeos). <b>DIFERENCIA = DIAN − HELISA "
        "conciliado</b>.")

    info_periodo = analisis.get("info_periodo") or {}
    st.caption(
        f"{analisis['empresa']} · NIT {analisis['nit']} · "
        f"PERIODO: {analisis['etiqueta']}")
    st.info(
        f"**Periodo detectado:** {info_periodo.get('descripcion', '')}. "
        "Se deduce de las fechas de emisión del reporte DIAN, las fechas de "
        "los documentos HELISA, los MESES SOLICITADOS, la fecha en que se "
        "elaboró el informe HELISA y la fecha de descarga del reporte DIAN.",
        icon=":material/event:")

    revisar = [r for r in resultados
               if estado_concepto(r, analisis["parametros"]) != "CONCILIADO"]
    partidas = partidas_para_revisar(analisis)
    total_docs = sum(len(r["dian"]) for r in resultados)

    # v6.13: resumen visual (dona de documentos DIAN por estado + datos).
    ok_docs = obs_docs = rev_docs = sin_docs = no_dian = 0
    for r in resultados:
        conteo = conteo_documentos(r)
        if conteo:
            ok, obs, rev, sin, solo = conteo
            ok_docs += ok
            obs_docs += obs
            rev_docs += rev
            sin_docs += sin
            no_dian += solo
        elif estado_concepto(r, analisis["parametros"]) == "CONCILIADO":
            ok_docs += len(r["dian"])
        else:
            rev_docs += len(r["dian"])
    # v6.16: la suma con signo de las diferencias de conceptos distintos
    # (ventas, compras, notas) se compensa entre si y no significa nada; se
    # muestra la suma de las diferencias en valor absoluto (lo que falta
    # por explicar en total).
    dif_total = sum(abs(r["diferencia_total"]) for r in resultados)
    conciliados = len(resultados) - len(revisar)
    panel_resumen(
        "Documentos del reporte DIAN",
        f"{analisis['etiqueta']} · {len(resultados)} conceptos",
        [("Conciliados", ok_docs, "ok"),
         ("Conciliados, revisar tercero", obs_docs, "info"),
         ("Por revisar", rev_docs, "alerta"),
         ("No contabilizados en HELISA", sin_docs, "error")],
        f"{total_docs:,}".replace(",", "."), "documentos DIAN",
        datos=[("Conceptos conciliados", f"{conciliados} de "
                f"{len(resultados)}"),
               ("Diferencias por explicar (suma absoluta)", _cop(dif_total)),
               ("Partidas para revisar", f"{len(partidas):,}".replace(
                   ",", ".")),
               ("Solo en HELISA (NO DIAN)", f"{no_dian:,}".replace(
                   ",", "."))])

    filas = []
    for r in resultados:
        estado = estado_concepto(r, analisis["parametros"])
        clase = "gm-dif-cero" if abs(r["diferencia_total"]) < 0.005 \
            else "gm-dif-no"
        iva = "—" if r["diferencia_iva"] is None else _cop(
            r["diferencia_iva"])
        filas.append(
            f"<tr><td><b>{r['concepto']['clave']}</b> · "
            f"{html.escape(r['concepto']['nombre'])}</td>"
            f"<td>{len(r['dian'])}</td>"
            f"<td>{_cop(r['total_dian'])}</td>"
            f"<td>{_cop(r['total_helisa'])}</td>"
            f"<td>{_cop(r['total_helisa_ajustado'])}</td>"
            f"<td class='{clase}'>{_cop(r['diferencia_total'])}</td>"
            f"<td>{iva}</td>"
            f"<td><span class='gm-estado "
            f"{'ok' if estado == 'CONCILIADO' else 'rev'}'>{estado}"
            f"</span></td></tr>")
    st.markdown(
        "<div class='gm-tabla-cont'><table class='gm-tabla'><thead><tr><th>Concepto</th>"
        "<th>Docs DIAN</th><th>Total DIAN</th><th>Total HELISA</th>"
        "<th>HELISA conciliado</th><th>Diferencia</th><th>Dif. IVA</th>"
        "<th>Estado</th></tr></thead><tbody>" + "".join(filas)
        + "</tbody></table></div>",
        unsafe_allow_html=True)
    _graficos_conceptos(resultados)

    st.write("")
    mime = ("application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Descargar formato completo",
            data=resultado["archivo"],
            file_name=resultado["nombre_archivo"],
            mime=mime, type="primary", use_container_width=True,
            key="dian_desc_completo",
            help="Archivo Excel con la estructura de la conciliación de la firma: "
                 "hoja DIAN original, hojas DIAN y HELISA por concepto con "
                 "sus totales y el resumen con partidas para revisar.")
    with d2:
        st.download_button(
            "Descargar formato simplificado",
            data=resultado["archivo_simplificado"],
            file_name=resultado["nombre_simplificado"],
            mime=mime, type="primary", use_container_width=True,
            key="dian_desc_simple",
            help="Una sola hoja: los documentos DIAN por concepto con "
                 "TOTAL, SISTEMA (HELISA) y DIFERENCIA, y una columna que "
                 "dice si cada documento está en el sistema.")

    # v6.14: panel de diferencias (antes: visor + lista de partidas).
    titulo_seccion(
        "Diferencias", 5,
        "Por concepto: <b>qué explica la diferencia</b> entre HELISA y la "
        "DIAN (en azul lo que la plataforma ya verificó y resta en el Excel; "
        "en ámbar lo que queda por revisar) y las <b>partidas</b> ordenadas "
        "por valor. Abre una partida para ver HELISA vs DIAN campo por "
        "campo. El visor con los documentos originales sigue disponible "
        "abajo.")
    mostrar_diferencias(panel_diferencias_dian(analisis), "dian_dif",
                        visor=lambda: visor_dian(resultado, con_titulo=False))

    for compras in [r for r in resultados if r["modo"] == "detalle"]:
        with st.expander(f"{compras['concepto']['nombre']}: cruce "
                         "documento por documento"):
            docs = compras["documentos_helisa"]
            conteo = Counter(d["estado"] for d in docs)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Iguales a DIAN", conteo["ok"])
            c2.metric("Redondeo", conteo["redondeo"])
            c3.metric("NO DIAN", conteo["no_dian"])
            c4.metric("Dif. de valor", conteo["diferencia"])
            st.dataframe(
                [{"Documento HELISA": d["documento"], "Fecha": d["fecha"],
                  "NIT": d["nit"], "Beneficiario": d["beneficiario"],
                  "Total HELISA": _cop(d["total_debito"]),
                  "IVA": _cop(d["iva"]),
                  "Resultado": observacion_documento(
                      d, compras["info_dian"]) or "OK"}
                 for d in docs],
                use_container_width=True, hide_index=True)

    if analisis["no_conciliados"]:
        with st.expander("Documentos DIAN no incluidos (informativo)"):
            st.caption("Tipos del reporte DIAN que no hacen parte de esta "
                       "conciliación (por ejemplo nómina electrónica y "
                       "eventos).")
            st.dataframe(
                [{"Grupo": n["grupo"], "Tipo de documento": n["tipo"],
                  "Cantidad": n["cantidad"], "Total": _cop(n["total"])}
                 for n in analisis["no_conciliados"]],
                use_container_width=True, hide_index=True)



def visor_dian(resultado, con_titulo=True):
    analisis = resultado["analisis"]
    if con_titulo:
        titulo_seccion(
            "Visor de diferencias", 5,
            "Muestra el <b>reporte DIAN</b> y el informe de <b>HELISA</b> "
            "completos, cada uno en su recuadro con desplazamiento propio y "
            "el número de fila del archivo. Cada diferencia tiene su "
            "<b>número y color</b> en los dos documentos. <b>Siguiente ▶</b> "
            "salta a la próxima marca solo en ese documento; <b>Ctrl + "
            "rueda</b> del mouse hace zoom. Pasa el mouse sobre una fila "
            "marcada para ver qué no cuadra y qué hacer.")
    try:
        diferencias = diferencias_dian(analisis)
    except Exception as error:
        st.caption(f"No se pudo preparar el visor: {error}")
        return
    conceptos = [c for c, items in diferencias.items() if items]
    if not conceptos:
        st.success("No hay diferencias para revisar: todo cruza. Los Excel "
                   "de la conciliación se generan igual y quedan como "
                   "soporte.")
        mime = ("application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Descargar formato completo", data=resultado["archivo"],
                file_name=resultado["nombre_archivo"], mime=mime,
                type="primary", use_container_width=True,
                key="dian_desc_completo_sin_dif")
        with d2:
            st.download_button(
                "Descargar formato simplificado",
                data=resultado["archivo_simplificado"],
                file_name=resultado["nombre_simplificado"], mime=mime,
                type="primary", use_container_width=True,
                key="dian_desc_simple_sin_dif")
        return

    nombres = {r["concepto"]["clave"]: r for r in analisis["resultados"]}
    clave = st.radio(
        "Concepto", conceptos, horizontal=True, key="dian_visor_concepto",
        format_func=lambda c: f"{c} · {len(diferencias[c])} diferencia"
                              f"{'s' if len(diferencias[c]) != 1 else ''}")
    clave = clave if clave in conceptos else conceptos[0]
    items = diferencias[clave]
    informe = nombres[clave]["informe"]

    tabla_d, numero_d = tabla_reporte_dian(analisis["reporte"])
    tabla_h, numero_h = tabla_informe_helisa(informe)
    marcas_d, marcas_h, tips = marcas_dian(items, numero_d, numero_h)

    solo = _filtro_visor("dian_visor_filtro")
    with st.expander(f"Leyenda ({len(items)} diferencias)", expanded=False):
        st.dataframe(
            [{"#": i["etiqueta"], "Diferencia": i["estado"],
              "Filas DIAN": ", ".join(map(str, i["filas_dian"][:6]))
              + ("…" if len(i["filas_dian"]) > 6 else ""),
              "Filas HELISA": ", ".join(map(str, i["filas_helisa"][:6]))
              + ("…" if len(i["filas_helisa"]) > 6 else ""),
              "Qué hacer": i["que_hacer"]} for i in items],
            use_container_width=True, hide_index=True)

    def panel(codigo, titulo, tabla, marcas):
        return {"codigo": codigo,
                "titulo": f"{titulo} · {len(marcas)} filas marcadas",
                "contenido": contenido_tabla_visor(tabla, marcas, tips,
                                                   solo)}

    _mostrar_visor([
        panel("DIAN", f"Reporte DIAN · "
                      f"{analisis['reporte'].get('archivo', '')}",
              tabla_d, marcas_d),
        panel("HELISA", f"HELISA · {informe.get('archivo', '')}", tabla_h,
              marcas_h)])


def modulo_dian():
    banner_modulo(
        "Módulo 3 · Impuestos",
        "Conciliación DIAN",
        "Concilia el reporte de documentos electrónicos descargado de la "
        "DIAN contra los comprobantes de diario de HELISA. Entrega dos "
        "archivos Excel: el formato completo de la firma (hojas por concepto, "
        "detalle HELISA marcado y resumen) y un formato simplificado de una "
        "sola hoja. El periodo (mes, corte o semana) se detecta solo.",
        ("Reporte DIAN + Comprobantes HELISA", "Salida: 2 formatos Excel",
         "Periodo automático"),
    )

    titulo_seccion(
        "Reporte de la DIAN", 1,
        "<b>Obligatorio.</b> Descárgalo del portal de <b>Facturación "
        "electrónica DIAN → Documentos → Listado</b> para el periodo a "
        "conciliar (mes completo, corte o semana), incluyendo "
        "<b>Emitidos</b> y <b>Recibidos</b>. Cárgalo <b>tal como se "
        "descarga</b>: el .zip del portal (o el .xlsx que trae adentro). "
        "Si descargaste el mismo periodo varias veces, carga todas las "
        "descargas: se unen y un documento repetido se toma de la descarga "
        "más reciente.")

    encabezado_carga(
        "DIAN", "Reporte de documentos electrónicos",
        "Obligatorio · .zip o .xlsx del portal · uno o varios",
        "El reporte se copia tal cual como primera hoja del resultado. Las "
        "hojas por concepto se arman filtrando por <b>Grupo</b> (Emitido / "
        "Recibido) y <b>Tipo de documento</b>. La fecha de descarga (en el "
        "nombre de la hoja, p. ej. Rp_Doc_20261001) ayuda a detectar el "
        "periodo.")
    archivo_dian = st.file_uploader(
        "Reporte DIAN", type=["zip", "xlsx", "xls", "csv", "xml"],
        key="dian_reporte", accept_multiple_files=True,
        on_change=invalidar_dian, label_visibility="collapsed")
    if archivo_dian is None:
        archivos_dian = []
    elif isinstance(archivo_dian, (list, tuple)):
        archivos_dian = list(archivo_dian)
    else:
        archivos_dian = [archivo_dian]

    reporte = None
    if archivos_dian:
        try:
            reporte = _leer_reportes_dian_cache(
                tuple((a.name, a.getvalue()) for a in archivos_dian))
            grupos = Counter(str(dato(reporte, r, "Grupo"))
                             for r in reporte["registros"])
            periodo = periodo_dian(reporte)
            if reporte["registros"]:
                st.success(
                    f"Reporte DIAN leído: {len(reporte['registros'])} "
                    f"documentos · " + " · ".join(
                        f"{g}: {n}" for g, n in grupos.items())
                    + (f" · Mes predominante: {etiqueta_periodo(periodo)} "
                       "(el periodo exacto se detecta al generar)"
                       if periodo else ""))
            if reporte.get("nota"):
                st.caption(reporte["nota"])
            for aviso in reporte.get("avisos", []):
                st.warning(aviso + " Si cargaste el reporte DIAN en otro "
                           "cuadro, cámbialo o activa «Ordenar "
                           "automáticamente» antes de generar.")
        except Exception as error:
            reporte = None
            st.warning(f"Este archivo no se pudo leer como reporte DIAN "
                       f"({error}). Si quedó en otro cuadro, cámbialo o "
                       "activa «Ordenar automáticamente»; si generas así, "
                       "se concilia contra un reporte vacío y se avisa.")

    with st.expander("Eventos posteriores (opcional · para acuses dados "
                     "después de la descarga)"):
        st.markdown(
            "Los acuses de una factura a crédito muchas veces se emiten "
            "días después. Si el reporte DIAN se descargó antes, esos "
            "eventos no aparecen y la factura sale <b>sin acuse</b>. Carga "
            "aquí un reporte DIAN <b>posterior</b> (p. ej. de los primeros "
            "días del mes siguiente): de él <b>solo se toman los eventos "
            "emitidos</b> por la empresa; sus facturas no se concilian.",
            unsafe_allow_html=True)
        archivos_eventos = st.file_uploader(
            "Reporte DIAN posterior", type=["zip", "xlsx", "xls", "csv"],
            key="dian_eventos", accept_multiple_files=True,
            on_change=invalidar_dian, label_visibility="collapsed") or []
    if archivos_eventos and reporte is not None:
        try:
            adicionales = []
            for extra in [_leer_reportes_dian_cache(((a.name, a.getvalue()),))
                          for a in archivos_eventos]:
                adicionales.extend(eventos_de_reporte(extra, "posterior"))
            # Copia: el reporte leido esta en cache y no se modifica.
            reporte = {**reporte, "eventos_adicionales": adicionales}
            st.caption(f"Eventos posteriores: {len(adicionales)} eventos "
                       "emitidos se usarán para los acuses.")
        except Exception as error:
            st.warning(f"No se pudo leer el reporte posterior ({error}).")

    titulo_seccion(
        "Comprobantes de HELISA", 2,
        "Puedes cargar <b>un solo archivo</b> con todos los documentos del "
        "periodo (la relación de documentos: se separa sola por concepto) o "
        "<b>un archivo por concepto</b>. En el segundo caso todos son "
        "<b>opcionales</b>, pero debes cargar <b>al menos uno</b> "
        "(FV, NCV, NDV, DSE, NADSE, NC o FC). Carga cada informe <b>tal como sale de "
        "HELISA</b>: en <b>PDF</b> o en <b>Excel 97-2003</b>; sirve el "
        "Comprobante diario - Detalle o el Resumen. Solo se concilian los "
        "conceptos cuyo informe cargues; si el reporte DIAN trae documentos "
        "de un concepto sin informe, se avisa.")

    archivos = {}
    detectados = []
    if "dian_modo_helisa" not in st.session_state:
        # Se recuerda la ultima forma de carga usada en este equipo.
        guardado = leer_config().get("dian_modo_helisa")
        st.session_state["dian_modo_helisa"] = guardado if guardado in (
            MODO_HELISA_UNO, MODO_HELISA_VARIOS) else MODO_HELISA_UNO

    def _al_cambiar_modo_helisa():
        invalidar_dian()
        guardar_config(dian_modo_helisa=st.session_state.get(
            "dian_modo_helisa"))
    modo_helisa = st.radio(
        "¿Cómo vas a cargar los informes de HELISA?",
        [MODO_HELISA_UNO, MODO_HELISA_VARIOS], horizontal=True,
        key="dian_modo_helisa", on_change=_al_cambiar_modo_helisa,
        help="Un solo archivo: el Comprobante diario - Detalle de HELISA con "
             "todos los tipos de documento del periodo (la relación de "
             "documentos del mes); se separa solo por concepto. Un archivo "
             "por concepto: un informe para FV, otro para DSE, etc.")
    if modo_helisa == MODO_HELISA_UNO:
        encabezado_carga(
            "TODOS", "Relación de documentos del periodo",
            "PDF o Excel 97-2003 de HELISA · Comprobante diario - Detalle "
            "con FEV, NCV, NDV, DSE/DSEC, NADSE, NDC y FC/FCC juntos",
            "Exporta desde HELISA el <b>Comprobante diario - Detalle</b> del "
            "periodo con <b>todos los tipos de documento</b> a la vez. La "
            "plataforma separa cada documento según su tipo (FEV → ventas, "
            "NCV → notas crédito de ventas, NDV → notas débito de ventas, "
            "DSE y DSEC → documentos soporte, NADSE → notas de ajuste DSE, "
            "NDC → notas crédito de proveedores, FC y FCC → compras) y "
            "concilia cada concepto como si se hubiera cargado aparte. "
            "También reconoce tipos propios de cada empresa (p. ej. EMPRESA B: "
            "FEDU, FECO, FEEX, FACT → ventas; NCFV, NCCO → notas crédito; "
            "NDFV, NDCO → notas débito; NADS → notas de ajuste). Un tipo que "
            "no reconoce se coteja con el reporte DIAN (NIT y folio, folio y "
            "valor, o NIT y valor) y se concilia en el concepto con el que "
            "cruce, con alerta para confirmarlo; si no cruza con nada (p. "
            "ej. CE, RC) se omite y se avisa.")
        combinado = st.file_uploader(
            "Relación de documentos HELISA", type=["pdf", "xls", "xml",
                                                   "xlsx"],
            key="dian_helisa_TODOS", on_change=invalidar_dian,
            label_visibility="collapsed")
        if combinado is not None:
            archivos[CLAVE_COMBINADO] = combinado
            try:
                with st.spinner("Separando los documentos por concepto…"):
                    filas, otros = _resumen_combinado_cache(
                        combinado.getvalue(), combinado.name)
                detectados = [c for c, _, _ in filas]
                # v6.13: un indicador por concepto (hasta 4 por fila).
                kpis([{"etiqueta": f"{concepto} · "
                                   f"{NOMBRE_CONCEPTO_CORTO.get(concepto, '')}",
                       "valor": f"{n} documento{'s' if n != 1 else ''}",
                       "detalle": formato_cop(total),
                       "icono": "recibo", "tono": "indigo"}
                      for concepto, n, total in filas],
                     columnas=min(4, max(1, len(filas))))
                if otros:
                    st.caption("Tipos no reconocidos: "
                               + ", ".join(f"{c} ({n})"
                                           for c, n in otros.items())
                               + ". Al generar se cotejan con el reporte "
                               "DIAN (NIT, folio, valor): los que crucen se "
                               "concilian en su concepto con alerta; los "
                               "demás se omiten y se avisa.")
            except Exception as error:
                # v6.11.3: si no se puede leer no se habilita la generacion
                # (antes fallaba despues con un error menos claro).
                archivos.pop(CLAVE_COMBINADO, None)
                st.warning(f"No se pudo separar el archivo por concepto: "
                           f"{error}")
    columnas = st.columns(2)
    cargas_visibles = CARGAS_HELISA if modo_helisa == MODO_HELISA_VARIOS \
        else []
    for i, carga in enumerate(cargas_visibles):
        with columnas[i % 2]:
            encabezado_carga(carga["clave"], carga["titulo"],
                             carga["informe"], carga["ayuda"])
            archivo = st.file_uploader(
                carga["titulo"], type=["pdf", "xls", "xml", "xlsx"],
                key=f"dian_helisa_{carga['clave']}",
                on_change=invalidar_dian, label_visibility="collapsed")
            if archivo is not None and not archivo.getvalue():
                # v6.11.3: archivo de 0 bytes (exportacion incompleta).
                st.error(f"«{archivo.name}» está vacío (0 bytes): vuelve a "
                         "exportarlo de HELISA, ábrelo para confirmar que "
                         "tiene datos y cárgalo de nuevo.")
            elif archivo is not None:
                archivos[carga["clave"]] = archivo
            st.write("")

    titulo_seccion(
        "Parámetros y generación", 3,
        "Los parámetros por defecto funcionan para el PUC colombiano y los "
        "informes estándar de HELISA. Puedes cambiar los tipos de documento "
        "DIAN por concepto, los ajustes a restar, las cuentas de IVA e "
        "impuesto al consumo, la tolerancia de redondeo y los prefijos de "
        "los acuses de facturas a crédito.")

    parametros = parametros_dian_ui(reporte)

    # v6.7: decision del usuario: usar cada archivo donde se cargo (por
    # defecto) u ordenarlos solos si parecen de otro cuadro.
    ordenar = st.toggle(
        "Ordenar automáticamente los archivos cargados en un cuadro que no "
        "les corresponde",
        value=bool(leer_config().get("dian_ordenar_automatico", False)),
        key="dian_ordenar_automatico",
        help="Apagado (recomendado): cada archivo se concilia en el cuadro "
             "donde lo cargaste; si parece de otro concepto solo se avisa. "
             "Encendido: si un informe parece de otro concepto (p. ej. FC "
             "cargado en NC) o el reporte DIAN quedó en un cuadro de HELISA, "
             "la plataforma los ubica sola y lo avisa.")
    if ordenar != bool(leer_config().get("dian_ordenar_automatico", False)):
        guardar_config(dian_ordenar_automatico=ordenar)
    listo = bool(archivos_dian) and bool(archivos)
    if st.button("Generar conciliación DIAN", type="primary",
                 use_container_width=True, disabled=not listo,
                 key="dian_generar"):
        invalidar_dian()
        try:
            with st.spinner("Leyendo informes, cruzando documentos y "
                            "armando el Excel..."):
                st.session_state["dian_resultado_gmya"] = \
                    generar_conciliacion_dian(
                        [(a.name, a.getvalue()) for a in archivos_dian],
                        {clave: (a.name, a.getvalue())
                         for clave, a in archivos.items()},
                        parametros,
                        nombre_dian=archivos_dian[0].name,
                        contenido_eventos=[(a.name, a.getvalue())
                                           for a in archivos_eventos],
                        ordenar_automatico=ordenar,
                    )
            st.toast("Conciliación DIAN lista: revisa el resumen y "
                     "descarga los Excel.")
        except Exception as error:
            reportar_error("No se pudo generar la conciliación DIAN", error)

    if not listo:
        falta = []
        if not archivos_dian:
            falta.append("el reporte DIAN (obligatorio)")
        if not archivos:
            falta.append("la relación de documentos de HELISA"
                         if modo_helisa == MODO_HELISA_UNO else
                         "al menos un informe HELISA: FV, NCV, NDV, DSE, "
                         "NADSE, NC o FC")
        st.caption("Para habilitar la generación falta cargar "
                   + " y ".join(falta) + ".")
    elif archivos:
        conceptos = detectados if CLAVE_COMBINADO in archivos else [
            c["clave"] for c in CARGAS_HELISA if c["clave"] in archivos]
        if conceptos:
            st.caption("Se conciliarán: " + ", ".join(conceptos)
                       + ". Los conceptos sin documentos no se incluyen.")

    resultado = st.session_state.get("dian_resultado_gmya")
    if resultado:
        avisos = resultado["analisis"]["avisos"]
        if avisos:
            st.warning(
                "**Revisa esto antes de usar la conciliación.** Se generó "
                "igual, pero los documentos tienen diferencias con lo "
                "esperado:\n\n" + "\n".join(f"- {a}" for a in avisos))
        else:
            st.success("Documentos reconocidos: cada informe coincide con "
                       "su concepto y con el reporte DIAN.")
        mostrar_resultado_dian(resultado)
