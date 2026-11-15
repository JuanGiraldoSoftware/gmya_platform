"""Pantalla "Conciliacion bancaria" (Streamlit). Contrato: modulo_conciliacion().

Depende de: gmya.comun.numeros, gmya.comun.grilla, gmya.comun.cache, gmya.ui.componentes, gmya.ui.visor, gmya.modulos.bancos.lectura, gmya.modulos.bancos.conciliacion, gmya.modulos.bancos.sugerencias, gmya.modulos.bancos.flexible, gmya.modulos.bancos.visor, gmya.ui.interfaz_comun, gmya.registro.interfaz
"""

import datetime
import html
from collections import Counter
from decimal import Decimal

import streamlit as st

from gmya.comun.numeros import formato_cop
from gmya.comun.grilla import tabla_desde_archivo
from gmya.comun.cache import _cache
from gmya.ui.componentes import banner_modulo, encabezado_carga, titulo_seccion
from gmya.ui.visor import (
    AMARILLO_VISOR, contenido_pdf_visor, contenido_tabla_visor,
    excel_resaltado, _hex, numero_fila, numero_pagina, _oscuro,
    paginas_resaltadas, pdf_resaltado, RESOLUCION_VISOR_COMPLETO,
)
from gmya.modulos.bancos.lectura import descripcion_periodo, etiqueta_fecha
from gmya.modulos.bancos.conciliacion import (
    agrupar_gastos_bancarios, avisos_totales, es_pdf, frase_resultado,
    UMBRAL_PAREJA_DUDOSA, UMBRAL_PAREJA_SEGURA,
)
from gmya.modulos.bancos.sugerencias import CONFIANZA_ORDEN
from gmya.modulos.bancos.flexible import generar_conciliacion_multiple
from gmya.modulos.bancos.visor import (
    diferencias_para_visor, grupos_cotejo, tips_cotejos,
)
from gmya.ui.interfaz_comun import _filtro_visor, _mostrar_visor
from gmya.registro.interfaz import reportar_error


# ============================================================
# INTERFAZ: CONCILIACION BANCARIA
# ============================================================
def invalidar_conciliacion():
    st.session_state.pop("conciliacion_gmya", None)
    st.session_state.pop("conciliacion_mensaje_gmya", None)


def lista_palabras(texto):
    return [p.strip() for p in str(texto or "").split(",") if p.strip()]


def modulo_conciliacion():
    banner_modulo(
        "Módulo 2 · Bancos",
        "Conciliación bancaria",
        "Cruza uno o varios extractos bancarios (cualquier banco) contra el "
        "HELISA, cuenta por cuenta, en PDF o Excel. "
        "Valida totales, empareja movimientos, arma el soporte de gastos "
        "bancarios y propone los ajustes. Si algo no cuadra, avisa pero no "
        "se detiene.",
        ("Varios extractos + HELISA", "Salida: Excel con soporte",
         "Sugerencias de ajuste"),
    )

    titulo_seccion(
        "Carga de documentos", 1,
        "Puedes cargar <b>varios extractos</b> (una cuenta por extracto) y "
        "uno o varios archivos de <b>HELISA</b> (cada uno puede traer varias "
        "cuentas). Formatos: <b>PDF</b> con texto o <b>Excel / CSV</b>. "
        "Cada extracto se empareja con su cuenta de HELISA por número de "
        "cuenta, saldos y valores. Cada archivo se usa <b>tal como se "
        "cargó</b> (extracto o HELISA): si su contenido parece del otro "
        "tipo solo se avisa. Si los documentos no parecen cuadrar se genera "
        "igual con una <b>advertencia</b>.")

    col_extracto, col_libro = st.columns(2)

    with col_extracto:
        encabezado_carga(
            "BANCO", "Extractos bancarios",
            "PDF o Excel · uno o varios",
            "<b>PDF</b>: se lee por la estructura de la tabla (fecha al "
            "inicio, valores a la derecha, saldo corrido). <b>Excel/CSV</b>: "
            "se buscan los encabezados FECHA, DESCRIPCIÓN y VALOR o "
            "DÉBITO/CRÉDITO, y SALDO si existe. En ambos casos se valida "
            "contra el saldo anterior, abonos, cargos y nuevo saldo. "
            "Carga todos los extractos del mes (ahorros, corriente...) a "
            "la vez.")
        pdf_extracto = st.file_uploader(
            "Extractos bancarios",
            type=["pdf", "xlsx", "xls", "xml", "csv"],
            accept_multiple_files=True,
            key="conc_pdf_extracto",
            on_change=invalidar_conciliacion,
            label_visibility="collapsed",
        )

    with col_libro:
        encabezado_carga(
            "HELISA", "Informe de bancos HELISA",
            "PDF o Excel 97-2003 · una o varias cuentas",
            "Informe de bancos de <b>HELISA</b> (Caja Bancos) en PDF o "
            "exportado a Excel. Si trae varias cuentas, cada una se cruza con el "
            "extracto que le corresponde (aunque el número venga escrito "
            "distinto, p. ej. 778-00002022 vs. 7780002022).")
        pdf_libro = st.file_uploader(
            "HELISA",
            type=["pdf", "xlsx", "xls", "xml", "csv"],
            accept_multiple_files=True,
            key="conc_pdf_libro",
            on_change=invalidar_conciliacion,
            label_visibility="collapsed",
        )

    titulo_seccion(
        "Parámetros de emparejamiento", 2,
        "Valores por defecto: ventana de <b>15 días</b> entre la fecha del "
        "banco y la de HELISA, y tolerancia de redondeo de <b>$0</b> "
        "(la conciliación debe cuadrar exacta, centavos incluidos). Las "
        "palabras clave adicionales amplían la clasificación de conceptos "
        "(GMF, comisiones, impuestos, seguridad social...).")

    with st.expander("Opciones avanzadas"):
        col_a, col_b = st.columns(2)

        ventana = col_a.number_input(
            "Ventana de fechas para emparejar (días)",
            min_value=0, max_value=90, value=15, step=1,
            help="Diferencia máxima entre la fecha del banco y la de HELISA.",
        )
        tolerancia = col_b.number_input(
            "Tolerancia de redondeo (COP)",
            min_value=0.0, max_value=1000.0, value=0.0, step=1.0,
            help="Por defecto 0: solo se emparejan valores exactos. Si se "
                 "sube, partidas con una diferencia menor o igual se "
                 "emparejan y se reportan como VALOR DIFERENTE (nunca como "
                 "conciliadas).",
        )

        st.caption(
            "Palabras clave adicionales, separadas por coma. El concepto se "
            "clasifica si CONTIENE la palabra (no hace falta el texto exacto)."
        )

        extra_bancarios = st.text_input(
            "Gastos bancarios", key="conc_kw_bancarios",
            placeholder="Ej.: tarifa, cuota, mantenimiento",
        )
        extra_impuestos = st.text_input(
            "Impuestos", key="conc_kw_impuestos",
            placeholder="Ej.: reteiva, consumo",
        )
        extra_seguridad = st.text_input(
            "Seguridad social", key="conc_kw_seguridad",
            placeholder="Ej.: colsubsidio",
        )

    titulo_seccion(
        "Generar", 3,
        "Prepara un Excel de <b>3 hojas</b>: <b>Resumen</b> (advertencias, "
        "saldos por cuenta, conciliación HELISA vs. extracto, gastos "
        "bancarios por categoría, desglose de comisiones, control del IVA "
        "y revisión de lectura), <b>Conciliación</b> (línea a línea por "
        "cuenta: <b>verde</b> = conciliada, <b>amarillo</b> = valor "
        "diferente, <b>rojo</b> = no está en uno de los dos) y <b>Detalle "
        "gastos</b> (GMF, comisiones, IVA e intereses del extracto y si ya "
        "están en HELISA).")

    extractos = list(pdf_extracto or [])
    libros = list(pdf_libro or [])
    if st.button(
        "Generar conciliación",
        type="primary",
        use_container_width=True,
        disabled=not (extractos or libros),
        key="conc_generar",
    ):
        invalidar_conciliacion()
        try:
            with st.spinner("Leyendo, emparejando cuentas y conciliando..."):
                st.session_state["visor_idx_gmya"] = 0
                st.session_state["conc_cuenta_idx_gmya"] = 0
                st.session_state["conciliacion_gmya"] = \
                    generar_conciliacion_multiple(
                        [(a.name, a.getvalue()) for a in extractos],
                        [(a.name, a.getvalue()) for a in libros],
                        ventana_dias=int(ventana),
                        tolerancia_redondeo=Decimal(str(tolerancia)),
                        palabras_extra={
                            "comision": lista_palabras(extra_bancarios),
                            "impuestos": lista_palabras(extra_impuestos),
                            "seguridad_social":
                                lista_palabras(extra_seguridad),
                        },
                    )
        except Exception as error:
            reportar_error("No se pudo generar la conciliación", error)

    if not (extractos or libros):
        st.caption("Carga al menos un extracto o un archivo de HELISA para habilitar la "
                   "generación. Lo ideal: todos los extractos del mes y el "
                   "HELISA.")
    elif not extractos or not libros:
        st.caption("Falta cargar " + ("los extractos" if not extractos
                                      else "HELISA")
                   + ": se puede generar igual, pero todo quedará como "
                     "pendiente en el otro documento.")

    resultado = st.session_state.get("conciliacion_gmya")
    if not resultado:
        return

    # v6.5: la descarga va PRIMERO, apenas hay resultado (cuadre o no), para
    # que nada de lo que se pinta despues pueda dejarla sin mostrar.
    _descarga_excel_bancos(resultado, "conc_desc_principal")

    # Advertencias justo debajo del boton: no bloquean, explican.
    avisos = avisos_totales(resultado)
    if avisos:
        st.warning(
            "**Revisa esto antes de usar la conciliación.** Se generó igual, "
            "pero los documentos tienen diferencias con lo esperado:\n\n"
            + "\n".join(f"- {a}" for a in avisos))
    else:
        st.success("Documentos reconocidos y cuentas emparejadas sin "
                   "problemas.")

    try:
        mostrar_resultado_bancos(resultado)
    except Exception as error:
        # El Excel ya se ofrecio arriba; el detalle en pantalla no lo bloquea.
        reportar_error("No se pudo mostrar el detalle de la conciliación "
                       "en pantalla (el Excel sí se generó)", error)


def _descarga_excel_bancos(resultado, clave):
    cuadra = all(c["analisis"]["conc"]["no_explicada"] == 0
                 for c in resultado["cuentas"])
    st.success("**Conciliación generada.** "
               + ("Todo cuadra: el Excel queda como soporte."
                  if cuadra else "Hay partidas por revisar: el detalle "
                  "está en el Excel y abajo en pantalla."))
    st.download_button(
        "Descargar conciliación en Excel",
        data=resultado["archivo"],
        file_name=resultado["nombre_archivo"],
        mime=("application/vnd.openxmlformats-officedocument."
              "spreadsheetml.sheet"),
        type="primary", use_container_width=True, key=clave)


def _nivel_pareja(cuenta):
    puntos = cuenta.get("puntaje")
    if puntos is None:
        return "Sin pareja"
    if puntos >= UMBRAL_PAREJA_SEGURA:
        return "Alta"
    if puntos >= UMBRAL_PAREJA_DUDOSA:
        return "Parcial"
    return "Baja (¿otra cuenta?)"


def _reiniciar_visor():
    st.session_state["visor_idx_gmya"] = 0


def mostrar_resultado_bancos(resultado):
    cuentas = resultado["cuentas"]
    titulo_seccion(
        "Resultado de la conciliación", 4,
        "Un renglón por cuenta: extracto y cuenta de HELISA emparejados, "
        "qué tan seguro es el emparejamiento, partidas pendientes y "
        "diferencias. Elige una cuenta para ver su detalle y el visor.")

    todas = [m for c in cuentas for m in c["analisis"]["movs"]]
    pendientes = sum(1 for m in todas if m["estado"] in (
        "sin_libro", "diferencia", "agrupado_diferencia"))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cuentas conciliadas", len(cuentas))
    m2.metric("Movimientos de extractos", len(todas))
    m3.metric("Pendientes o con diferencia", pendientes)
    m4.metric("Diferencia sin explicar", formato_cop(sum(
        (c["analisis"]["conc"]["no_explicada"] for c in cuentas),
        Decimal("0"))))

    st.dataframe(
        [{"Cuenta": c["etiqueta"],
          "Extracto": c["archivo_extracto"] or "(ninguno)",
          "Cuenta de HELISA": c["analisis"]["seccion"].get("etiqueta")
          or "(ninguna)",
          "Coincidencia": _nivel_pareja(c),
          "Movimientos": len(c["analisis"]["movs"]),
          "Diferencia de saldo final": formato_cop(
              c["analisis"]["conc"]["saldo_fin_ext"]
              - c["analisis"]["conc"]["saldo_fin_lib"]),
          "Sin explicar": formato_cop(c["analisis"]["conc"]["no_explicada"])}
         for c in cuentas],
        use_container_width=True, hide_index=True)


    indice = 0
    if len(cuentas) > 1:
        indice = st.selectbox(
            "Cuenta para ver el detalle y el visor",
            list(range(len(cuentas))), key="conc_cuenta_idx_gmya",
            format_func=lambda k: (
                f"{cuentas[k]['etiqueta']} · "
                f"{cuentas[k]['archivo_extracto'] or 'sin extracto'}"),
            on_change=_reiniciar_visor)
    _detalle_cuenta(cuentas[indice % len(cuentas)])


def _detalle_cuenta(resultado):
    analisis = resultado["analisis"]
    extracto = analisis["extracto"]
    movs = analisis["movs"]
    libro_movs = analisis["libro_movs"]
    conc = analisis["conc"]
    validaciones = analisis["validaciones"]
    pendientes_validacion = [v for v in validaciones if v[3] != "OK"]
    tipo_periodo, rango, _ = descripcion_periodo(*extracto["periodo"])

    titulo_seccion(
        f"Detalle de la cuenta {resultado.get('etiqueta', '')}", None,
        "<b>Contabilizados</b>: movimientos del extracto encontrados en "
        "HELISA (incluye gastos bancarios registrados en una sola nota). "
        "<b>Pendientes o con diferencia</b>: sin registro en HELISA o con "
        "valor distinto. La <b>diferencia de saldo final</b> es extracto "
        "menos HELISA.")

    st.caption(
        f"{extracto['banco']} · Cuenta {extracto['tipo_cuenta']} "
        f"{extracto['cuenta'] or ''} · {tipo_periodo} ({rango}) · "
        f"{analisis['libro']['empresa']}"
    )

    contar = Counter(m["estado"] for m in movs)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Movimientos del extracto", len(movs))
    m2.metric(
        "Contabilizados",
        contar["conciliado"] + contar["agrupado"],
    )
    m3.metric(
        "Pendientes o con diferencia",
        contar["sin_libro"] + contar["diferencia"]
        + contar["agrupado_diferencia"],
    )
    m4.metric(
        "Diferencia de saldo final",
        formato_cop(conc["saldo_fin_ext"] - conc["saldo_fin_lib"]),
    )

    # v6.5: movimientos agrupados (cuadran, pero se avisa como se cruzaron).
    notas_grupo = []
    for m in movs:
        if m.get("grupo_nm") and m["nota"] not in notas_grupo:
            notas_grupo.append(m["nota"])
    if notas_grupo:
        st.info("**Movimientos agrupados (conciliados):** cuadran exacto, "
                "pero no uno a uno.\n\n"
                + "\n".join(f"- {n.replace('MOVIMIENTO AGRUPADO: ', '')}"
                             for n in notas_grupo)
                + "\n\nEn el Excel salen como **CONCILIADA (AGRUPADA)** con "
                  "esta misma nota.", icon=":material/merge:")

    if analisis["seccion"].get("vacia"):
        st.info("Esta cuenta no tiene HELISA: todos sus movimientos "
                "quedan como NO ESTÁ EN HELISA.")
    elif extracto.get("vacio"):
        st.info("Esta cuenta de HELISA no tiene extracto: sus registros "
                "quedan como NO ESTÁ EN EL EXTRACTO.")
    elif pendientes_validacion:
        st.warning(
            "Hay controles por revisar antes de usar el reporte: "
            + "; ".join(v[0] for v in pendientes_validacion)
            + ". Consulta el bloque 7 de la hoja Resumen del Excel."
        )
    else:
        st.success(
            "Extracto y HELISA leídos completos: los totales cuadran y la "
            "conciliación de saldos cierra sin diferencia sin explicar."
        )

    sugerencias = analisis.get("sugerencias", [])
    conteo_conf = Counter(s["confianza"] for s in sugerencias)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Sugerencias", len(sugerencias))
    s2.metric("Confianza alta", conteo_conf["Alta"])
    s3.metric("Confianza media", conteo_conf["Media"])
    s4.metric("Sin causa típica", conteo_conf["Baja"])

    with st.expander(f"Sugerencias ({len(sugerencias)})",
                     expanded=bool(sugerencias)):
        if sugerencias:
            st.dataframe(
                [{"ID": s["id"], "Tipo": s["tipo"],
                  "Confianza": s["confianza"],
                  "Explicación": s["explicacion"], "Qué hacer": s["accion"],
                  "Diferencia": formato_cop(s["diferencia"])}
                 for s in sorted(sugerencias, key=lambda s: (
                     -CONFIANZA_ORDEN[s["confianza"]], s["id"]))],
                use_container_width=True, hide_index=True)
        else:
            st.caption("No hay partidas pendientes.")

    if sugerencias:
        with st.expander("Análisis detallado: qué no cuadra y de dónde salen "
                         "los cálculos"):
            st.caption(
                "Elige una partida para ver las pruebas que se hicieron "
                "para encontrar la causa.")
            elegida = st.selectbox(
                "Sugerencia", sugerencias, key="conc_analisis_sel",
                format_func=lambda s: f"{s['id']} · {s['tipo']} · "
                                      f"{s['confianza']}")
            st.markdown(f"**Qué no cuadra.** {elegida['que_no_cuadra']}")
            st.dataframe(
                [{"Prueba / cálculo": c[0], "Operación": c[1],
                  "Resultado": c[2], "¿Explica?": c[3]}
                 for c in elegida["calculos"]],
                use_container_width=True, hide_index=True)
            st.markdown(f"**Conclusión: qué podría ser.** "
                        f"{elegida['explicacion']}")
            st.markdown(f"**Qué hacer.** {elegida['accion']}")
            for a in elegida["ajustes"]:
                st.markdown(f"**Ajuste propuesto.** Débito {a['debito']} / "
                            f"Crédito {a['credito']}: "
                            f"{formato_cop(a['valor'])}")
            st.caption("Aporte a la diferencia de saldos (extracto − "
                       f"HELISA): {formato_cop(elegida['efecto_saldo'])}")

    with st.expander("Partidas del extracto pendientes o con diferencia"):
        filas = [
            {
                "Fecha": etiqueta_fecha(m["fecha"]),
                "Ubicación": m.get("ubicacion") or "",
                "Movimiento": m["descripcion"],
                "Valor": formato_cop(m["valor"]),
                "Categoría": m["categoria_nombre"],
                "Estado": frase_resultado(m),
            }
            for m in movs
            if m["estado"] in ("sin_libro", "diferencia",
                               "agrupado_diferencia")
        ]
        if filas:
            st.dataframe(filas, use_container_width=True, hide_index=True)
        else:
            st.caption("Todos los movimientos del extracto están "
                       "contabilizados.")

    with st.expander("Registros de HELISA sin movimiento en el extracto"):
        filas = [
            {
                "Fecha": etiqueta_fecha(m["fecha"]),
                "Documento": f"{m['tipo']} {m['numero']}",
                "Ubicación": m.get("ubicacion") or "",
                "Tercero": m["tercero"],
                "Valor para el banco": formato_cop(m["valor"]),
            }
            for m in libro_movs if m["estado"] == "sin_extracto"
        ]
        if filas:
            st.dataframe(filas, use_container_width=True, hide_index=True)
        else:
            st.caption("Todos los registros de HELISA aparecen en el "
                       "extracto.")

    with st.expander("Gastos bancarios identificados"):
        st.dataframe(
            [
                {
                    "Concepto": g["concepto"],
                    "Cantidad": g["cantidad"],
                    "Valor por cargo": (
                        formato_cop(g["unitario"])
                        if g["unitario"] is not None else "Variable"
                    ),
                    "Total": formato_cop(g["total"]),
                    "Pendiente de contabilizar":
                        formato_cop(g["total_pendiente"]),
                }
                for g in agrupar_gastos_bancarios(movs)
            ],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Controles de validación"):
        def mostrar(valor):
            return formato_cop(valor) if isinstance(valor, Decimal) \
                else str(valor)

        st.dataframe(
            [
                {
                    "Control": control,
                    "Esperado": mostrar(esperado),
                    "Obtenido": mostrar(obtenido),
                    "Estado": estado,
                }
                for control, esperado, obtenido, estado, _ in validaciones
            ],
            use_container_width=True,
            hide_index=True,
        )

    visor_diferencias(resultado)


# ============================================================
# INTERFAZ: VISOR DE DIFERENCIAS (CONCILIACION BANCARIA)
# ============================================================

def _claves_movimientos(movimientos, es_libro):
    """Representacion hashable de las partidas (para la cache)."""
    claves = []
    for m in movimientos:
        claves.append((
            m.get("pagina"), m.get("ubicacion"), m["fecha"].isoformat(),
            str(m["valor"]),
            m.get("tipo", "") if es_libro else "",
            str(m.get("numero", "")) if es_libro else "",
            m.get("descripcion", "") if not es_libro else "",
            tuple(m.get("_color") or ()), m.get("_etiqueta", "")))
    return tuple(claves)


def _movimientos_de_claves(claves):
    return [{"pagina": c[0], "ubicacion": c[1],
             "fecha": datetime.date.fromisoformat(c[2]),
             "valor": Decimal(c[3]), "tipo": c[4], "numero": c[5],
             "descripcion": c[6], "_color": c[7] or None,
             "_etiqueta": c[8]} for c in claves]


@_cache
def _paginas_resaltadas_cache(contenido, claves, es_libro, resolucion=None):
    return paginas_resaltadas(contenido, _movimientos_de_claves(claves),
                              es_libro, resolucion)


@_cache
def _pdf_resaltado_cache(contenido, claves, es_libro):
    return pdf_resaltado(contenido, _movimientos_de_claves(claves),
                         es_libro)


@_cache
def _excel_resaltado_cache(contenido, filas):
    return excel_resaltado(contenido, list(filas))


def _descarga_resaltada(etiqueta, contenido, movimientos, es_libro, clave,
                        nombre_base):
    if contenido is None:
        return
    try:
        if es_pdf(contenido):
            datos = _pdf_resaltado_cache(
                contenido, _claves_movimientos(movimientos, es_libro),
                es_libro)
            nombre, mime = f"{nombre_base}_resaltado.pdf", "application/pdf"
        else:
            filas = tuple(sorted({
                (numero_fila(m), tuple(m.get("_color") or AMARILLO_VISOR),
                 m.get("_etiqueta", "")) for m in movimientos
                if numero_fila(m)}))
            datos = _excel_resaltado_cache(contenido, filas)
            nombre = f"{nombre_base}_resaltado.xlsx"
            mime = ("application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet")
    except Exception as error:
        st.caption(f"No se pudo preparar la copia resaltada: {error}")
        return
    st.download_button(etiqueta, data=datos, file_name=nombre, mime=mime,
                       key=clave, use_container_width=True)


def _marcas_filas(movimientos):
    """{fila: (color, etiqueta)} para el visor de Excel/CSV."""
    marcas = {}
    for m in movimientos:
        fila = numero_fila(m)
        if fila and fila not in marcas:
            marcas[fila] = (m.get("_color") or AMARILLO_VISOR,
                            m.get("_etiqueta", ""))
    return marcas


def _leyenda_cotejos(grupos):
    """Tabla: numero y color de cada cotejo, que hay en cada documento."""
    def lado_extracto(g):
        return "<br>".join(
            f"{html.escape(m['descripcion'][:45])} · "
            f"{formato_cop(m['valor'])} · {m.get('ubicacion') or ''}"
            for m in g["extracto"]) or "<i>No está en el extracto</i>"

    def lado_libro(g):
        return "<br>".join(
            f"{html.escape(l['tipo'])} {html.escape(str(l['numero']))} "
            f"{html.escape(l['tercero'][:30])} · {formato_cop(l['valor'])} "
            f"· {l.get('ubicacion') or ''}"
            for l in g["libro"]) or "<i>No está en HELISA</i>"

    filas = []
    for g in grupos:
        filas.append(
            f"<tr><td><span class='gm-cotejo' style='background:"
            f"{_hex(_oscuro(g['color'], 0.7))}'>{g['etiqueta']}</span>"
            f"<span class='gm-muestra-mini' style='background:"
            f"{_hex(g['color'])}'></span></td>"
            f"<td><b>{html.escape(g['estado'])}</b>"
            f"{'<br>' + html.escape(g['tipo'].capitalize()) if g['tipo'] else ''}"
            f"</td><td>{lado_extracto(g)}</td><td>{lado_libro(g)}</td></tr>")
    st.markdown(
        "<div class='gm-leyenda'><table><thead><tr><th>Cotejo</th>"
        "<th>Resultado</th><th>Extracto</th><th>HELISA</th></tr>"
        "</thead><tbody>" + "".join(filas) + "</tbody></table></div>",
        unsafe_allow_html=True)


def _panel_visor_banco(codigo, titulo, contenido, resaltar, es_libro, tips,
                       solo):
    panel = {"codigo": codigo,
             "titulo": f"{titulo} · {len(resaltar)} partidas marcadas"}
    if contenido is None:
        panel["contenido"] = ("<p class='gv-vacio'>No se cargó este "
                              "documento para esta cuenta.</p>")
        return panel
    try:
        if es_pdf(contenido):
            paginas = _paginas_resaltadas_cache(
                contenido, _claves_movimientos(resaltar, es_libro), es_libro,
                RESOLUCION_VISOR_COMPLETO)
            esperadas = Counter(numero_pagina(m) or 1 for m in resaltar)
            panel["contenido"] = contenido_pdf_visor(paginas, tips, solo,
                                                     esperadas)
        else:
            panel["contenido"] = contenido_tabla_visor(
                tabla_desde_archivo(contenido), _marcas_filas(resaltar),
                tips, solo)
    except Exception as error:
        panel["contenido"] = (f"<p class='gv-vacio'>No se pudo mostrar el "
                              f"documento: {html.escape(str(error))}</p>")
    return panel


def visor_diferencias(resultado):
    analisis = resultado["analisis"]
    documentos = resultado.get("documentos", {})
    diferencias = diferencias_para_visor(analisis)

    titulo_seccion(
        "Visor de diferencias", 5,
        "Muestra el <b>extracto</b> y <b>HELISA</b> completos, tal como "
        "llegaron, cada uno en su recuadro: se desplazan por separado. Cada "
        "<b>cotejo</b> tiene su <b>color y número</b> en los dos documentos. "
        "<b>Siguiente ▶</b> salta a la próxima marca solo en ese documento; "
        "<b>Ctrl + rueda</b> del mouse hace zoom dentro del documento. Pasa "
        "el mouse sobre una marca para ver qué no cuadra y qué hacer.")

    if not diferencias:
        st.success("No hay diferencias para revisar: todo cruza. El Excel "
                   "de la conciliación se genera igual y queda como "
                   "soporte.")
        general = st.session_state.get("conciliacion_gmya") or {}
        if general.get("archivo"):
            st.download_button(
                "Descargar conciliación en Excel",
                data=general["archivo"],
                file_name=general.get("nombre_archivo")
                or "Conciliacion.xlsx",
                mime=("application/vnd.openxmlformats-officedocument."
                      "spreadsheetml.sheet"),
                type="primary", use_container_width=True,
                key="conc_desc_sin_diferencias")
        return

    grupos = grupos_cotejo(analisis, False)
    tips = tips_cotejos(grupos)

    def unicos(lista):
        vistos, salida = set(), []
        for m in lista:
            if id(m) not in vistos:
                vistos.add(id(m))
                salida.append(m)
        return salida

    resaltar_e = unicos([m for g in grupos for m in g["extracto"]])
    resaltar_l = unicos([l for g in grupos for l in g["libro"]])

    solo = _filtro_visor("visor_filtro_gmya")
    with st.expander(f"Leyenda: qué se cotejó con qué ({len(grupos)} "
                     "cotejos)", expanded=False):
        st.caption("Cada número tiene el mismo color en el extracto y en "
                   "HELISA. Si un lado dice 'No está', esa partida solo "
                   "aparece en el otro documento.")
        _leyenda_cotejos(grupos)

    _mostrar_visor([
        _panel_visor_banco("BANCO", "Extracto bancario",
                           documentos.get("extracto"), resaltar_e, False,
                           tips, solo),
        _panel_visor_banco("HELISA", "HELISA", documentos.get("libro"),
                           resaltar_l, True, tips, solo)])

    with st.expander("Descargar los documentos con las partidas "
                     "resaltadas"):
        d1, d2 = st.columns(2)
        with d1:
            _descarga_resaltada("Extracto resaltado",
                                documentos.get("extracto"), resaltar_e,
                                False, "desc_ext_resaltado", "Extracto")
        with d2:
            _descarga_resaltada("HELISA resaltado", documentos.get("libro"),
                                resaltar_l, True, "desc_lib_resaltado",
                                "HELISA")
