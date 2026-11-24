"""Pantalla "Planillas de seguridad social" (Streamlit). Contrato: modulo_planillas().

Depende de: gmya.ui.componentes, gmya.modulos.planillas.logica
"""

import streamlit as st

from gmya.comun.texto import comparable
from gmya.ui.visual import grafico, html_barras, kpis

from gmya.ui.componentes import banner_modulo, encabezado_carga, titulo_seccion
from gmya.modulos.planillas.logica import (
    agregar_plantilla, eliminar_plantilla, generar_resultados,
    invalidar_resultado, procesar_planilla,
)


# ============================================================
# INTERFAZ: PLANILLAS DE SEGURIDAD SOCIAL
# ============================================================
def modulo_planillas():
    banner_modulo(
        "Módulo 1 · Seguridad social",
        "Planillas de seguridad social",
        "Organiza los registros de las planillas PILA en TXT: un archivo por "
        "cotizante o agrupaciones personalizadas, conservando siempre la "
        "cabecera de la planilla de origen.",
        ("Entrada: TXT PILA", "Salida: ZIP de TXT", "Proceso local"),
    )

    # ============================================================
    # CARGA DE PLANILLAS
    # ============================================================

    titulo_seccion(
        "Carga de planillas", 1,
        "Puedes cargar <b>varias planillas TXT</b> a la vez. La primera "
        "línea de cada archivo es la <b>cabecera</b> y se copia en cada TXT "
        "generado. Los registros se agrupan por el <b>número de "
        "documento</b> del cotizante (001-CC-123..., 001CC123..., sin "
        "importar el tipo de documento).")

    encabezado_carga(
        "PILA", "Planillas TXT", "Una o varias planillas del período",
        "Codificación aceptada: UTF-8, Windows-1252 o Latin-1. Las líneas "
        "sin documento reconocible se informan como <b>advertencia</b> en "
        "el informe de procesamiento.")
    archivos = st.file_uploader(
        "Selecciona las planillas TXT",
        type=["txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if archivos:
        st.caption(f"Planillas seleccionadas: {len(archivos)}")

        if st.button(
            "Procesar planillas",
            type="primary",
            use_container_width=True,
        ):
            procesadas = []
            errores = []

            for archivo in archivos:
                try:
                    procesadas.append(procesar_planilla(archivo))
                except Exception as error:
                    errores.append(f"{archivo.name}: {error}")

            for error in errores:
                st.error(error)

            if procesadas:
                st.session_state["planillas_gmya"] = procesadas
                st.session_state["plantillas_gmya"] = []
                st.session_state["siguiente_id_plantilla"] = 1
                st.session_state["mensaje_gmya"] = ""
                st.session_state["modalidad_gmya"] = "Individualizar"

                invalidar_resultado()

                st.success(
                    f"Se procesaron {len(procesadas)} planillas."
                )

    # ============================================================
    # ORGANIZACION DE PERSONAS
    # ============================================================

    if "planillas_gmya" in st.session_state:
        planillas = st.session_state["planillas_gmya"]

        titulo_seccion(
            "Organización de personas", 2,
            "<b>Individualizar</b>: un TXT por persona. <b>Selección "
            "personalizada</b>: eliges qué cotizantes van juntos en un TXT "
            "compuesto (plantilla); los no asignados se individualizan "
            "automáticamente. Cada persona solo puede estar en una plantilla "
            "dentro de su planilla de origen.")

        modalidad = st.radio(
            "Selecciona la modalidad",
            options=[
                "Individualizar",
                "Seleccion personalizada",
            ],
            format_func=lambda opcion: (
                "Individualizar: un TXT por persona"
                if opcion == "Individualizar"
                else "Seleccion personalizada: elegir personas para cada TXT"
            ),
            key="modalidad_gmya",
        )

        if modalidad == "Seleccion personalizada":
            st.write(
                "Selecciona una planilla, busca cotizantes por nombre "
                "o cédula y agrupa las personas que quieras en un TXT. "
                "Las personas restantes se generarán individualmente."
            )

            indice_planilla = st.selectbox(
                "Planilla de origen",
                options=list(range(len(planillas))),
                format_func=lambda i: planillas[i]["origen"],
                key="fuente_seleccionada_gmya",
            )

            planilla = planillas[indice_planilla]

            asignadas = {
                (p["indice_planilla"], identificacion)
                for p in st.session_state.get("plantillas_gmya", [])
                for identificacion in p["identificaciones"]
            }

            disponibles = [
                identificacion
                for identificacion in planilla["grupos"]
                if (indice_planilla, identificacion) not in asignadas
            ]

            etiquetas = {}

            for identificacion in disponibles:
                nombre = (
                    planilla["nombres"].get(identificacion, "")
                    or "NOMBRE NO IDENTIFICADO"
                )

                etiquetas[identificacion] = (
                    f"{nombre} | Documento: {identificacion}"
                )

            clave_seleccion = f"seleccion_personas_{indice_planilla}"
            clave_nombre = f"nombre_plantilla_{indice_planilla}"

            st.multiselect(
                "Buscar y seleccionar personas por nombre o cédula",
                options=disponibles,
                format_func=lambda identificacion: etiquetas.get(
                    identificacion,
                    identificacion,
                ),
                key=clave_seleccion,
                placeholder="Escribe un nombre o numero de documento...",
                help=(
                    "Selecciona varias personas para incluirlas en el "
                    "mismo TXT. Se conservaran todos sus registros."
                ),
            )

            st.text_input(
                "Nombre del TXT compuesto",
                key=clave_nombre,
                placeholder="Ejemplo: PERSONAL_ADMINISTRATIVO",
                help=(
                    "Este sera el nombre del TXT que contendra "
                    "las personas seleccionadas."
                ),
            )

            st.button(
                "Agregar seleccion como plantilla",
                type="primary",
                use_container_width=True,
                on_click=agregar_plantilla,
                args=(
                    indice_planilla,
                    clave_seleccion,
                    clave_nombre,
                ),
            )

            mensaje = st.session_state.get("mensaje_gmya", "")

            if mensaje:
                st.info(mensaje)

            st.markdown("**Plantillas preparadas**")

            plantillas = st.session_state.get("plantillas_gmya", [])

            if not plantillas:
                st.caption(
                    "Todavia no has agregado plantillas. "
                    "Si generas los resultados ahora, todas las personas "
                    "se individualizaran."
                )
            else:
                for plantilla in plantillas:
                    indice = plantilla["indice_planilla"]
                    fuente = planillas[indice]["origen"]

                    col_info, col_boton = st.columns([5, 1])

                    with col_info:
                        st.write(
                            f"**{plantilla['nombre']}.TXT** · "
                            f"{len(plantilla['identificaciones'])} personas"
                        )
                        st.caption(f"Planilla de origen: {fuente}")

                        for identificacion in plantilla["identificaciones"]:
                            nombre = planillas[indice]["nombres"].get(
                                identificacion,
                                "",
                            )

                            st.text(
                                f"{nombre or 'NOMBRE NO IDENTIFICADO'} "
                                f"| Documento: {identificacion}"
                            )

                    with col_boton:
                        st.button(
                            "Eliminar",
                            key=f"eliminar_plantilla_{plantilla['id']}",
                            on_click=eliminar_plantilla,
                            args=(plantilla["id"],),
                        )

            st.caption(
                "Cada persona solo puede asignarse una vez dentro de "
                "su planilla de origen. Las personas no asignadas se "
                "generaran automaticamente en TXT individuales."
            )

        else:
            total_personas = sum(
                len(planilla["grupos"])
                for planilla in planillas
            )

            st.info(
                f"Se generara un TXT por persona. "
                f"Personas identificadas: {total_personas}."
            )

        titulo_seccion(
            "Generar TXT", 3,
            "Genera los TXT y un <b>INFORME_PROCESAMIENTO.TXT</b> con el "
            "conteo de personas, registros y advertencias por planilla. "
            "Los nombres de archivo usan el nombre del cotizante en "
            "MAYÚSCULAS; si se repite se agrega (2), (3)...")

        if st.button(
            "Generar TXT y preparar descarga",
            type="primary",
            use_container_width=True,
        ):
            plantillas = st.session_state.get("plantillas_gmya", [])

            st.session_state["resultado_gmya"] = generar_resultados(
                planillas=planillas,
                modalidad=modalidad,
                plantillas=plantillas,
            )

    # ============================================================
    # RESULTADOS Y DESCARGA
    # ============================================================

    if "resultado_gmya" in st.session_state:
        resultado = st.session_state["resultado_gmya"]

        titulo_seccion(
            "Resultado del procesamiento", 4,
            "Las <b>advertencias</b> corresponden a líneas sin documento "
            "reconocible: no se incluyen en ningún TXT. Revísalas en el "
            "informe de procesamiento.")

        # v6.16: indicadores y graficos del procesamiento.
        adv = resultado["advertencias"]
        kpis([
            {"etiqueta": "Personas identificadas", "valor": f"{resultado['personas']:,}".replace(",", "."),
             "icono": "personas", "tono": "indigo"},
            {"etiqueta": "Registros agrupados", "valor": f"{resultado['registros']:,}".replace(",", "."),
             "icono": "capas", "tono": "teal"},
            {"etiqueta": "TXT generados", "valor": f"{resultado['cantidad_txt']:,}".replace(",", "."),
             "icono": "archivo", "tono": "magenta"},
            {"etiqueta": "Advertencias", "valor": str(adv), "icono": "alerta",
             "tono": "ambar" if adv else "verde",
             "estado": "alerta" if adv else "ok",
             "detalle": "Líneas sin documento: van al TXT de revisión"
             if adv else "Todas las líneas tienen documento"}])
        _graficos_planillas(st.session_state.get("planillas_gmya") or [])

        st.success(
            f"Proceso finalizado. Se generaron "
            f"{resultado['cantidad_txt']} TXT."
        )

        st.download_button(
            "Descargar resultados en ZIP",
            data=resultado["zip"],
            file_name="GMYA_planillas_procesadas.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

        with st.expander("Consultar nombres de los TXT"):
            for nombre in resultado["nombres"]:
                st.text(nombre)

        with st.expander("Informe de procesamiento"):
            st.text(resultado["informe"])


def _graficos_planillas(planillas):
    """v6.16: registros por planilla, cotizantes con novedades (mas de un
    registro en la planilla) y buscador de cotizantes."""
    if not planillas:
        return
    por_planilla = [(p["origen"], sum(len(v) for v in p["grupos"].values()))
                    for p in planillas]
    tramos = {"1 registro": 0, "2 registros": 0, "3 o más registros": 0}
    filas = []
    for p in planillas:
        for ident, lineas in p["grupos"].items():
            n = len(lineas)
            tramos["1 registro" if n == 1 else "2 registros" if n == 2
                   else "3 o más registros"] += 1
            filas.append({"Documento": ident,
                          "Nombre": p["nombres"].get(ident) or "",
                          "Planilla": p["origen"], "Registros": n})
    c1, c2 = st.columns(2)
    with c1:
        grafico("Registros por planilla", html_barras(por_planilla),
                icono_nombre="documentos")
    with c2:
        con_nov = tramos["2 registros"] + tramos["3 o más registros"]
        grafico("Cotizantes por número de registros", html_barras(
            list(tramos.items())), nota=f"{con_nov} con varias líneas "
            "(novedades: ingreso, retiro, variaciones…)",
            icono_nombre="personas")
    buscar = st.text_input("Buscar cotizante", key="pla_buscar",
                           placeholder="Documento o parte del nombre")
    if buscar:
        b = comparable(buscar)
        vista = [f for f in filas if b in comparable(
            f"{f['Documento']} {f['Nombre']}")]
        st.caption(f"{len(vista)} de {len(filas)} cotizantes.")
        st.dataframe(vista[:500], use_container_width=True, hide_index=True)
