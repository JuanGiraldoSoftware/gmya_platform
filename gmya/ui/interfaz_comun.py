"""Filtro y visor de diferencias compartidos por las pantallas de
conciliacion (bancos y DIAN).

Depende de: gmya.ui.visor
"""

import streamlit as st

from gmya.ui.visor import html_visor_documentos


def _mostrar_visor(paneles, alto=720):
    """Dibuja el visor (componente HTML con su propio desplazamiento)."""
    import streamlit.components.v1 as componentes
    componentes.html(html_visor_documentos(paneles, alto),
                     height=alto + 190, scrolling=False)


def _filtro_visor(clave):
    filtro = st.radio(
        "Qué mostrar en el visor",
        ["Mostrar todo", "Mostrar solo las marcadas"], horizontal=True,
        key=clave, label_visibility="collapsed",
        help="Mostrar todo: el documento completo con las marcas. Solo las "
             "marcadas: únicamente las páginas (PDF) o filas (Excel) que "
             "tienen alguna marca.")
    return filtro.endswith("marcadas")
