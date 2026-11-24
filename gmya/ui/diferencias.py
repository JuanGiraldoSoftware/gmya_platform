"""Panel de diferencias (v6.14): vista principal de los resultados de las
conciliaciones y revisiones, en lugar del visor de documentos.

Por concepto (o cuenta / empresa): resumen oscuro con dona, composicion de
la diferencia (explicada vs por revisar), barra de filtros (busqueda,
causas, orden) y lista de partidas con el detalle A vs B al abrirlas.
El visor de documentos queda disponible bajo demanda ("Ver los documentos
originales") para ubicar la fila exacta en el archivo.

Contrato:
  mostrar_diferencias(conceptos, clave, visor=None)
      conceptos: lista con el modelo de gmya/ui/visual.py (panel de
      diferencias). clave: prefijo unico para los widgets. visor: funcion
      sin argumentos que dibuja el visor original (opcional).
Depende de: gmya.ui.visual
"""

import streamlit as st

from gmya.comun.texto import comparable
from gmya.ui.visual import (
    completar_composicion, html_composicion, html_grupos, html_panel_resumen,
    html_partidas, pendiente_de, pesos,
)

POR_PAGINA = 25
ORDENES = ["Mayor diferencia", "Documento", "Causa"]


def _etiqueta_pestana(c):
    pend = pendiente_de(c)
    if abs(pend) < 0.005 and not c.get("partidas"):
        return f"{c['clave']} · cuadra"
    # Los centavos nunca se esconden (tolerancia 0).
    return f"{c['clave']} · {pesos(pend, decimales=abs(pend - round(pend)) >= 0.005)}"


def _lista(c, clave):
    partidas = c.get("partidas") or []
    if not partidas:
        if c.get("grupos"):
            st.markdown(html_grupos(c["grupos"]), unsafe_allow_html=True)
        return
    causas = sorted({p["causa"] for p in partidas})
    f1, f2, f3 = st.columns([2, 2, 1])
    with f1:
        texto = st.text_input(
            "Buscar", key=f"{clave}_buscar", placeholder="Documento, tercero "
            "o NIT", label_visibility="collapsed")
    with f2:
        elegidas = st.multiselect(
            "Causas", causas, default=causas, key=f"{clave}_causas",
            label_visibility="collapsed", placeholder="Todas las causas")
    with f3:
        ordenes = ["Mayor valor"] + ORDENES[1:] if c.get("revision") \
            else ORDENES
        orden = st.selectbox("Orden", ordenes, key=f"{clave}_orden",
                             label_visibility="collapsed")
    buscado = comparable(texto or "")
    vista = [p for p in partidas
             if (not elegidas or p["causa"] in elegidas)
             and (not buscado or buscado in comparable(
                 f"{p['titulo']} {p.get('sub', '')} {p.get('nota', '')}"))]
    if orden == "Documento":
        vista.sort(key=lambda p: comparable(p["titulo"]))
    elif orden == "Causa":
        vista.sort(key=lambda p: (p["causa"], -abs((p.get("a") or 0)
                                                   - (p.get("b") or 0))))
    else:
        vista.sort(key=lambda p: -abs((p.get("a") or 0) - (p.get("b") or 0)))
    llave = f"{clave}_n"
    n = st.session_state.get(llave, POR_PAGINA)
    st.markdown(html_partidas(vista[:n]), unsafe_allow_html=True)
    st.markdown(f'<div class="gm-pa-pie">Mostrando {min(n, len(vista))} de '
                f'{len(vista)} partidas · clic en una partida para ver el '
                f'detalle.</div>', unsafe_allow_html=True)
    if len(vista) > n:
        st.button(f"Mostrar {min(POR_PAGINA, len(vista) - n)} más",
                  key=f"{clave}_mas", on_click=lambda: st.session_state
                  .__setitem__(llave, n + POR_PAGINA))
    if c.get("grupos"):
        st.markdown(html_grupos(c["grupos"]), unsafe_allow_html=True)


def _concepto(c, clave):
    completar_composicion(c)
    st.markdown(html_panel_resumen(
        f"{c['clave']} · {c['nombre']}" if c.get("nombre") else c["clave"],
        c.get("sub", ""), c.get("dona") or [], c.get("centro", ""),
        c.get("centro_sub", ""), datos=c.get("datos") or ()),
        unsafe_allow_html=True)
    st.markdown(html_composicion(c), unsafe_allow_html=True)
    _lista(c, clave)


def mostrar_diferencias(conceptos, clave, visor=None):
    conceptos = [c for c in conceptos if c]
    if not conceptos:
        st.info("No hay diferencias para mostrar.")
        return
    if len(conceptos) == 1:
        _concepto(conceptos[0], f"{clave}_0")
    else:
        for i, (c, pestana) in enumerate(zip(conceptos, st.tabs(
                [_etiqueta_pestana(completar_composicion(c))
                 for c in conceptos]))):
            with pestana:
                _concepto(c, f"{clave}_{i}")
    if visor is not None:
        st.write("")
        if st.toggle("Ver los documentos originales con las marcas",
                     key=f"{clave}_visor",
                     help="Abre el visor de documentos (más lento): el "
                          "archivo tal como se cargó, con cada diferencia "
                          "marcada en su fila o página."):
            visor()
