"""Componentes visuales HTML reutilizables (Streamlit).

Contrato (pintan con st.markdown):
  banner_modulo(eyebrow, titulo, descripcion, chips=(), icono=None,
                tono=None)  (v6.15: vuelve el encabezado de v6.11 con el
                logo; icono/tono se aceptan pero no se dibujan)
  titulo_seccion(texto, numero=None, explicacion=None)
  encabezado_carga(codigo, titulo, detalle, explicacion)
  tarjeta(titulo, cuerpo, etiqueta="", oscura=False, explicacion=None,
          color=None, clase="", icono=None, tono="magenta")
  ayuda(texto, clase="") -> html del icono "?" con su globo (no pinta).
  _glosario_pp(campos) -> fila de etiquetas con el "?" de cada campo de una
                          tabla de revision; campos = [(nombre, html)].

Depende de: gmya.config, gmya.ui.visual
"""

import html

import streamlit as st

from gmya.config import LOGO_NOMBRE_B64, logo_b64
from gmya.ui.visual import icono as _icono

# (palabra del titulo, icono, tono) para los encabezados de modulo.
ICONO_MODULO = [
    ("DIAN", "recibo", "indigo"), ("bancaria", "banco", "teal"),
    ("Planillas", "personas", "verde"), ("pagos de nómina", "nomina", "ambar"),
    ("nómina", "nomina", "ambar"), ("Programación", "pagos", "magenta"),
    ("Odoo", "subir", "pizarra"), ("Búsqueda", "buscar", "magenta"),
    ("error", "bicho", "pizarra"), ("Uso", "grafico", "magenta"),
    ("usuario", "usuario", "pizarra"), ("computador", "usuario", "pizarra"),
    ("automatización", "rayo", "magenta"),
]
# Codigo de la cabecera de carga -> icono y tono.
ICONO_CARGA = {
    "DIAN": ("recibo", "indigo"), "HELISA": ("capas", "teal"),
    "TODOS": ("documentos", "teal"), "ANT": ("reloj", "pizarra"),
    "MOV": ("balanza", "teal"), "PDF": ("archivo", "magenta"),
    "XLS": ("archivo", "verde"), "TXT": ("archivo", "pizarra"),
}


def _icono_de(texto, tabla, defecto=("archivo", "magenta")):
    for clave, ico, tono in tabla:
        if clave.lower() in str(texto).lower():
            return ico, tono
    return defecto


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


def banner_modulo(eyebrow, titulo, descripcion, chips=(), icono=None,
                  tono=None):
    """Encabezado de pagina (diseno v6.11, restaurado en v6.15): bloque
    oscuro con degradado hacia el magenta, logo de la firma, titulo,
    descripcion y metadatos. El primer chip va resaltado. icono y tono se
    aceptan por compatibilidad (ya no se dibujan)."""
    chips_html = "".join(
        f'<span class="gm-chip {"m" if i == 0 else ""}">{c}</span>'
        for i, c in enumerate(chips))
    logo = logo_b64("logo_gma_nombre_claro.png", LOGO_NOMBRE_B64)
    st.markdown(
        f'<div class="gm-banner"><div class="gm-banner-fila">'
        f'<img src="data:image/png;base64,{logo}" alt="GMYA">'
        f'<div class="gm-sep"></div>'
        f'<div style="flex:1;min-width:260px">'
        f'<div class="gm-eyebrow">{eyebrow}</div>'
        f'<h1>{titulo}</h1><p>{descripcion}</p>'
        f'<div class="gm-chips">{chips_html}</div></div></div></div>',
        unsafe_allow_html=True,
    )


def encabezado_carga(codigo, titulo, detalle, explicacion):
    ico, tono = ICONO_CARGA.get(str(codigo).upper(), ("archivo", "pizarra"))
    st.markdown(
        f'<div class="gm-carga"><span class="gm-carga-ico t-{tono}">'
        f'{_icono(ico, 18)}</span><span class="gm-carga-txt">'
        f'<span>{titulo} <span class="gm-cod">{codigo}</span></span>'
        f'<small>{detalle}</small></span>{ayuda(explicacion)}</div>',
        unsafe_allow_html=True,
    )


def tarjeta(titulo, cuerpo, etiqueta="", oscura=False, explicacion=None,
            color=None, clase="", icono=None, tono="magenta"):
    etq = f'<span class="gm-etq">{etiqueta}</span>' if etiqueta else ""
    if icono:
        etq = (f'<span class="gm-tarj-ico t-{tono}">{_icono(icono, 20)}'
               f'</span>' + (f'<br>{etq}' if etq else ""))
    if color:
        titulo = (f'<span class="gm-muestra" style="background:{color}">'
                  f'</span>{titulo}')
    tip = ayuda(explicacion, "claro") if explicacion else ""
    st.markdown(
        f'<div class="gm-tarjeta {"oscura" if oscura else ""} {clase}">{etq}'
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
