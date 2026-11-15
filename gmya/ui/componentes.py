"""Componentes visuales HTML reutilizables (Streamlit).

Contrato (pintan con st.markdown):
  banner_modulo(eyebrow, titulo, descripcion, chips=())
  titulo_seccion(texto, numero=None, explicacion=None)
  encabezado_carga(codigo, titulo, detalle, explicacion)
  tarjeta(titulo, cuerpo, etiqueta="", oscura=False, explicacion=None,
          color=None)
  ayuda(texto, clase="") -> html del icono "?" con su globo (no pinta).
  _glosario_pp(campos) -> fila de etiquetas con el "?" de cada campo de una
                          tabla de revision; campos = [(nombre, html)].

Depende de: gmya.config
"""

import html

import streamlit as st

from gmya.config import logo_b64, LOGO_NOMBRE_B64


# ============================================================
# COMPONENTES VISUALES
# ============================================================
def ayuda(texto, clase=""):
    """Icono (?) con explicacion al pasar el cursor."""
    return (f'<span class="gm-ayuda {clase}" tabindex="0">?'
            f'<span class="gm-ayuda-texto">{texto}</span></span>')


def titulo_seccion(texto, numero=None, explicacion=None):
    num = f'<span class="gm-num">{numero}</span>' if numero else ""
    tip = ayuda(explicacion) if explicacion else ""
    st.markdown(
        f'<div class="gm-seccion">{num}<span class="gm-tit">{texto}</span>'
        f'{tip}</div>',
        unsafe_allow_html=True,
    )


def banner_modulo(eyebrow, titulo, descripcion, chips=()):
    chips_html = "".join(
        f'<span class="gm-chip {"m" if i == 0 else ""}">{c}</span>'
        for i, c in enumerate(chips))
    logo = logo_b64("logo_gma_nombre_claro.png", LOGO_NOMBRE_B64)
    st.markdown(
        f"""
        <div class="gm-banner">
          <div class="gm-banner-fila">
            <img src="data:image/png;base64,{logo}" alt="GMYA">
            <div class="gm-sep"></div>
            <div style="flex:1;min-width:260px">
              <div class="gm-eyebrow">{eyebrow}</div>
              <h1>{titulo}</h1>
              <p>{descripcion}</p>
              <div class="gm-chips">{chips_html}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def encabezado_carga(codigo, titulo, detalle, explicacion):
    st.markdown(
        f'<div class="gm-carga"><span class="gm-cod">{codigo}</span>'
        f'<span>{titulo}<br><small>{detalle}</small></span>'
        f'{ayuda(explicacion)}</div>',
        unsafe_allow_html=True,
    )


def tarjeta(titulo, cuerpo, etiqueta="", oscura=False, explicacion=None,
            color=None):
    etq = f'<span class="gm-etq">{etiqueta}</span>' if etiqueta else ""
    if color:
        titulo = (f'<span class="gm-muestra" style="background:{color}">'
                  f'</span>{titulo}')
    tip = ayuda(explicacion, "claro") if explicacion else ""
    st.markdown(
        f'<div class="gm-tarjeta {"oscura" if oscura else ""}">{etq}'
        f'<h3>{titulo}{tip}</h3>{cuerpo}</div>',
        unsafe_allow_html=True,
    )


def _glosario_pp(campos):
    """Fila de etiquetas con el (?) de cada campo de la tabla de revision."""
    chips = "".join(
        f'<span class="gm-glo-chip">{html.escape(nombre)}'
        f'{ayuda(texto, "izq" if i < 3 else "")}</span>'
        for i, (nombre, texto) in enumerate(campos))
    st.markdown(f'<div class="gm-glosario"><span class="gm-glo-tit">Campos '
                f'de la tabla</span>{chips}</div>', unsafe_allow_html=True)
