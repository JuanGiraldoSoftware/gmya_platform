"""Pantalla "Reportar un error" (Streamlit).

Contrato:
  modulo_reporte() -> formulario con: archivos usados para generar el
      resultado, archivo generado por la plataforma y una breve descripcion.
      Al enviar se crea una carpeta por reporte en
      SISTEMAS / REPORTES DE ERRORES GMYA TOOLS del Drive (o queda en el
      equipo y se sube la proxima vez si no hay Drive).
  En el registro de uso solo queda "reporte enviado" con la cantidad de
  archivos (sin nombres ni contenido).

Depende de: gmya.config, gmya.ui.componentes, gmya.registro.logica,
gmya.registro.interfaz, gmya.modulos.reporte.logica
"""

import streamlit as st

from gmya.config import VERSION
from gmya.ui.componentes import banner_modulo, encabezado_carga, titulo_seccion
from gmya.registro.logica import codigo_equipo, MODULOS_NOMBRE, nombre_equipo
from gmya.registro.interfaz import registrar_uso, reportar_error
from gmya.modulos.reporte.logica import (
    CARPETA_REPORTES, carpeta_reportes, guardar_reporte, subir_pendientes,
)

MINIMO_DESCRIPCION = 15


def modulo_reporte():
    banner_modulo(
        "Soporte",
        "Reportar un error",
        "Si un resultado salió mal o la plataforma mostró un error, envíalo "
        "aquí con los archivos que usaste y el que generó la plataforma. El "
        "reporte queda en el Drive de la firma para revisarlo y corregirlo.",
        ("Va a SISTEMAS del Drive", "Con tus archivos",
         "Breve descripción"))
    carpeta = st.session_state.get("reg_carpeta")
    destino = carpeta_reportes(carpeta) if carpeta else None
    if destino is None:
        st.warning("No se encontró la carpeta «GMYA Tools» del Drive en este "
                   "equipo: el reporte se guardará en el equipo y se subirá "
                   "solo la próxima vez que haya conexión con el Drive.")
    else:
        try:
            if subir_pendientes(carpeta):
                st.info("Se subieron al Drive reportes que habían quedado "
                        "guardados en este equipo.")
        except Exception:
            pass

    n = st.session_state.get("reporte_n", 0)
    origen = st.session_state.get("reporte_origen") or ""
    opciones = [k for k in MODULOS_NOMBRE if k not in ("reporte",)]
    titulo_seccion("Datos del error", 1,
                   "En qué módulo pasó y qué esperabas que saliera.")
    modulo = st.selectbox(
        "Módulo donde ocurrió", opciones,
        index=opciones.index(origen) if origen in opciones else 0,
        format_func=lambda k: MODULOS_NOMBRE.get(k, k),
        key=f"reporte_modulo_{n}")
    descripcion = st.text_area(
        "Breve descripción del error",
        placeholder="Ej.: En la conciliación DIAN de ECOTEC de octubre la "
                    "factura FE-72 sale como no contabilizada pero sí está "
                    "en HELISA.",
        key=f"reporte_descripcion_{n}", height=130)

    titulo_seccion("Archivos", 2,
                   "Adjunta los mismos archivos que cargaste y el archivo "
                   "que entregó la plataforma, para poder repetir el caso.")
    c1, c2 = st.columns(2)
    with c1:
        encabezado_carga("USADOS", "Archivos usados para generar el reporte",
                         "Uno o varios · cualquier formato",
                         "Los archivos que cargaste en el módulo (HELISA, "
                         "reporte DIAN, extractos, planillas...).")
        usados = st.file_uploader("Archivos usados",
                                  accept_multiple_files=True,
                                  key=f"reporte_usados_{n}",
                                  label_visibility="collapsed") or []
    with c2:
        encabezado_carga("GENERADO", "Archivo generado por la plataforma",
                         "Uno o varios · cualquier formato",
                         "El Excel, ZIP o TXT que descargaste de la "
                         "plataforma (si llegó a generarse).")
        generados = st.file_uploader("Archivo generado",
                                     accept_multiple_files=True,
                                     key=f"reporte_generados_{n}",
                                     label_visibility="collapsed") or []

    errores = st.session_state.get("reg_errores_sesion") or []
    if errores:
        st.caption(f"Se adjuntarán también los últimos {len(errores)} "
                   "errores que mostró la plataforma en esta sesión.")

    falta = []
    if len((descripcion or "").strip()) < MINIMO_DESCRIPCION:
        falta.append("una breve descripción (al menos "
                     f"{MINIMO_DESCRIPCION} caracteres)")
    if not usados:
        falta.append("los archivos usados")
    if falta:
        st.caption("Para enviar falta: " + " y ".join(falta) + ". El archivo "
                   "generado es opcional si la plataforma no llegó a "
                   "generarlo.")
    if st.button("Enviar reporte", type="primary", disabled=bool(falta),
                 use_container_width=True, key=f"reporte_enviar_{n}"):
        try:
            with st.spinner("Guardando el reporte en el Drive..."):
                ruta, en_drive = guardar_reporte(
                    carpeta,
                    {"persona": st.session_state.get("reg_persona", ""),
                     "modulo": MODULOS_NOMBRE.get(modulo, modulo),
                     "descripcion": descripcion, "version": VERSION,
                     "equipo": codigo_equipo(),
                     "nombre_equipo": nombre_equipo(),
                     "errores": list(errores)},
                    [(f.name, f.getvalue()) for f in usados],
                    [(f.name, f.getvalue()) for f in generados])
            registrar_uso("reporte", f"reporte de error enviado · "
                          f"{len(usados)} usados, {len(generados)} "
                          "generados")
            st.session_state["reporte_ok"] = (
                f"Reporte enviado: carpeta «{ruta.name}» en "
                f"SISTEMAS / {CARPETA_REPORTES}." if en_drive else
                f"Sin conexión con el Drive: el reporte quedó guardado en "
                f"este equipo («{ruta.name}») y se subirá solo la próxima "
                "vez.")
            st.session_state["reporte_n"] = n + 1
            st.rerun()
        except Exception as error:
            reportar_error("No se pudo guardar el reporte", error)
    aviso = st.session_state.pop("reporte_ok", None)
    if aviso:
        st.success(aviso)
