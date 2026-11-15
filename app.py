"""GMYA TOOLS · Plataforma de automatizacion contable
Giraldo Mosquera y Asociados SAS

Punto de entrada de Streamlit. Streamlit vuelve a ejecutar ESTE archivo en
cada interaccion; los modulos de gmya/ se importan una sola vez.

Orden de cada ejecucion:
  1. configuracion de la pagina, bloqueo de traduccion y estilos
  2. usuario del equipo + registro de uso
  3. menu lateral (MENU = gmya.modulos.inicio.MODULOS; "uso" para admin en
     su propia seccion "Administracion")
  4. barra superior: boton "Reportar un error" (o "Volver" desde el
     reporte), fijo en la franja oscura de arriba
  5. pantalla del modulo elegido (PANTALLAS)
  6. pie de pagina con la VERSION

Ejecutar en desarrollo:  streamlit run app.py
Ejecutable (.exe):       run_gmyatools.py lo lanza (ver README).
"""

import sys
from collections import OrderedDict

import streamlit as st

from gmya.config import (
    FIRMA, icono_pagina, logo_b64, LOGO_GMA_B64, PRODUCTO, RAZON_SOCIAL,
    VERSION,
)
from gmya.ui.estilos import aplicar_estilos
from gmya.ui.globos import _bloquear_traduccion
from gmya.registro.logica import es_admin, MODULOS_NOMBRE
from gmya.registro.interfaz import (
    AVISO_REGISTRO, _estado_registro, _instalar_registro_en_streamlit,
    _latido_registro, modulo_uso, pantalla_quien_usa, registrar_uso,
    tarjeta_persona_lateral,
)
from gmya.modulos.planillas.interfaz import modulo_planillas
from gmya.modulos.bancos.interfaz import modulo_conciliacion
from gmya.modulos.dian.interfaz import modulo_dian
from gmya.modulos.busqueda.interfaz import (
    modulo_busqueda, precalentar_indice_drive,
)
from gmya.modulos.pagos.interfaz import modulo_prog_pagos
from gmya.modulos.odoo.interfaz import modulo_odoo
from gmya.modulos.nomina.interfaz import modulo_nomina
from gmya.modulos.reporte.interfaz import modulo_reporte
from gmya.modulos.inicio import (
    ICONOS_MODULO, ir_a, modulo_inicio, MODULOS, PANTALLAS_FUERA_DEL_MENU,
)


def _relanzar_con_streamlit():
    """
    Si el archivo se ejecuta con 'python app.py' (modo "bare"),
    Streamlit no abre la interfaz y solo muestra avisos de
    'missing ScriptRunContext'. En ese caso se relanza solo con
    'streamlit run', que abre la plataforma en el navegador.
    """
    import os
    import subprocess
    if __name__ != "__main__" or os.environ.get("GMYA_RELANZADO"):
        return
    try:
        from streamlit import runtime
        if runtime.exists():
            return                      # ya corre con 'streamlit run'
    except Exception:
        return
    os.environ["GMYA_RELANZADO"] = "1"
    print("Abriendo GMYA Tools con Streamlit (streamlit run)...")
    # Sin vigilar cambios del codigo (no hace falta en uso diario y
    # consume CPU) y sin volver a ejecutar al guardar.
    opciones = ["--server.fileWatcherType", "none",
                "--server.runOnSave", "false"]
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run",
                              os.path.abspath(__file__)] + opciones
                             + sys.argv[1:]))


_relanzar_con_streamlit()


st.set_page_config(
    page_title="GMYA | Plataforma de automatización contable",
    page_icon=icono_pagina(),
    layout="wide",
    initial_sidebar_state="expanded",
)


_bloquear_traduccion()

# Hoja de estilos de la marca (antes era un st.markdown suelto
# en el monolito; ahora vive en gmya/ui/estilos.py).
aplicar_estilos()


# ============================================================
# NAVEGACION (MENU LATERAL)
# ============================================================
if "modulo_gmya" not in st.session_state:
    st.session_state["modulo_gmya"] = "inicio"

# Usuario del equipo y registro de uso (sin credenciales).
_carpeta_reg, _persona_reg = _estado_registro()


_instalar_registro_en_streamlit()
st.session_state["reg_interacciones"] = \
    st.session_state.get("reg_interacciones", 0) + 1
if st.session_state.get("reg_admin_de") != _persona_reg:
    st.session_state["reg_admin_de"] = _persona_reg
    st.session_state["reg_admin"] = bool(_persona_reg) and \
        es_admin(_persona_reg, _carpeta_reg)
MENU = OrderedDict(MODULOS)
ADMIN = OrderedDict()
if st.session_state.get("reg_admin"):
    ADMIN["uso"] = "Uso de la plataforma"
if st.session_state["modulo_gmya"] not in \
        set(MENU) | set(ADMIN) | set(PANTALLAS_FUERA_DEL_MENU):
    st.session_state["modulo_gmya"] = "inicio"


def _boton_menu(clave, nombre):
    opciones_boton = dict(
        key=f"menu_{clave}",
        type="primary" if st.session_state["modulo_gmya"] == clave
        else "secondary",
        on_click=ir_a,
        args=(clave,),
        use_container_width=True,
    )
    try:
        st.button(nombre, icon=ICONOS_MODULO[clave], **opciones_boton)
    except TypeError:
        # Versiones de Streamlit sin iconos en botones.
        st.button(nombre, **opciones_boton)


def _volver_del_reporte():
    origen = st.session_state.get("reporte_origen") or "inicio"
    if origen not in set(MENU) | set(ADMIN):
        origen = "inicio"
    st.session_state["modulo_gmya"] = origen


def _barra_superior():
    """v6.8: boton de soporte fijo en la franja oscura de arriba (CSS
    .gm-marca-barra en gmya/ui/estilos.py), separado del menu de modulos.
    Desde el reporte, el mismo lugar ofrece volver al modulo de origen."""
    st.markdown('<span class="gm-marca-barra"></span>',
                unsafe_allow_html=True)
    if st.session_state["modulo_gmya"] == "reporte":
        origen = st.session_state.get("reporte_origen") or "inicio"
        nombre = (MENU.get(origen) or ADMIN.get(origen) or "Inicio")
        args = dict(key="barra_volver", on_click=_volver_del_reporte,
                    help="Cierra el reporte sin enviarlo y vuelve al "
                         "módulo donde estabas.")
        try:
            st.button(f"Volver a {nombre}", icon=":material/arrow_back:",
                      **args)
        except TypeError:
            st.button(f"← Volver a {nombre}", **args)
    else:
        args = dict(key="barra_reportar", on_click=ir_a, args=("reporte",),
                    help="¿Un resultado salió mal o apareció un error? "
                         "Envíalo a sistemas con los archivos que usaste.")
        try:
            st.button("Reportar un error", icon=":material/bug_report:",
                      **args)
        except TypeError:
            st.button("Reportar un error", **args)


with st.sidebar:
    st.markdown(
        f'<img class="gm-side-logo" src="data:image/png;base64,'
        f'{logo_b64("logo_gma_claro.png", LOGO_GMA_B64)}" alt="GMYA">'
        f'<div class="gm-side-firma">{RAZON_SOCIAL}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="gm-side-titulo">Menú de herramientas</div>',
                unsafe_allow_html=True)
    for clave, nombre in MENU.items():
        _boton_menu(clave, nombre)
    if ADMIN:
        st.markdown('<div class="gm-side-titulo">Administración</div>',
                    unsafe_allow_html=True)
        for clave, nombre in ADMIN.items():
            _boton_menu(clave, nombre)
    st.markdown(
        '<div class="gm-side-nota"><b>¿Cómo funciona?</b><br>'
        'Cada módulo: cargar → parámetros → generar → revisar y descargar. '
        'Pasa el cursor por los íconos <b>?</b> para ver la explicación de '
        'cada paso.<br><br><b>Privacidad:</b> los documentos se procesan en '
        'este equipo; no se envían a servicios externos. ' + AVISO_REGISTRO
        + '</div>',
        unsafe_allow_html=True,
    )
    if _persona_reg:
        tarjeta_persona_lateral(_persona_reg, _carpeta_reg)
        _latido_registro()

PANTALLAS = {
    "inicio": modulo_inicio,
    "planillas": modulo_planillas,
    "bancos": modulo_conciliacion,
    "dian": modulo_dian,
    "busqueda": modulo_busqueda,
    "pagos": modulo_prog_pagos,
    "odoo": modulo_odoo,
    "nomina": modulo_nomina,
    "uso": modulo_uso,
    "reporte": modulo_reporte,
}
if not _persona_reg:
    pantalla_quien_usa(_carpeta_reg)
elif st.session_state.get("reg_cambiando") and \
        st.session_state.get("reg_equipo_admin"):
    pantalla_quien_usa(_carpeta_reg, modo_admin=True)
else:
    if not st.session_state.get("reg_inicio"):
        st.session_state["reg_inicio"] = True
        registrar_uso("inicio", f"Streamlit {getattr(st, '__version__', '')}")
    if st.session_state.get("reg_modulo") != st.session_state["modulo_gmya"]:
        st.session_state["reg_modulo"] = st.session_state["modulo_gmya"]
        registrar_uso("módulo", MODULOS_NOMBRE.get(
            st.session_state["modulo_gmya"], ""))
    precalentar_indice_drive()
    _barra_superior()
    PANTALLAS.get(st.session_state["modulo_gmya"], modulo_inicio)()


# ============================================================
# PIE DE PAGINA
# ============================================================
st.markdown(
    f"""
    <div class="gm-footer">
        <b>{FIRMA}</b> · {RAZON_SOCIAL} · {PRODUCTO} {VERSION}<br>
        Procesamiento local de documentos contables. Verifica siempre los
        resultados antes de registrarlos o presentarlos.
    </div>
    """,
    unsafe_allow_html=True,
)
