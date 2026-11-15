"""Hoja de estilos de la marca GMYA (carbon #272526 + magenta #E0118F).

Contrato:
  CSS_GMYA           texto <style> completo.
  aplicar_estilos()  lo inyecta; app.py lo llama en cada ejecucion (Streamlit
                     vuelve a ejecutar app.py en cada interaccion).

Depende de: (solo biblioteca estandar / terceros)
"""

import streamlit as st


# ============================================================
# DISENO (marca GMYA: carbon #272526 + magenta #E0118F)
# ============================================================
CSS_GMYA = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800;900&display=swap');

    /* componente invisible que bloquea la traduccion automatica */
    div[data-testid="stElementContainer"]:has(iframe[height="0"]),
    div.element-container:has(iframe[height="0"]) { display: none; }

    :root {
        --gm-tinta: #161415;
        --gm-carbon: #272526;
        --gm-grafito: #3D393B;
        --gm-humo: #5C5759;
        --gm-magenta: #E0118F;
        --gm-magenta-oscuro: #A30A67;
        --gm-magenta-claro: #FF8AD0;
        --gm-rosa: #FFE3F3;
        --gm-papel: #EEE9EC;
        --gm-blanco: #FFFFFF;
        --gm-verde: #1F7A3A;
        --gm-rojo: #B00020;
        --gm-sombra: 5px 5px 0 var(--gm-carbon);
    }

    html, body, [class*="css"], .stApp, button, input, textarea, select {
        font-family: 'Montserrat', 'Segoe UI', Arial, sans-serif;
    }

    /* Fondo con la trama de puntos del logo */
    .stApp {
        background-color: var(--gm-papel);
        background-image: radial-gradient(rgba(224,17,143,.16) 1.6px,
                                          transparent 1.7px);
        background-size: 22px 22px;
        color: var(--gm-tinta);
    }
    [data-testid="stHeader"] {
        background: var(--gm-carbon);
        border-bottom: 4px solid var(--gm-magenta);
    }
    [data-testid="stHeader"] * { color: var(--gm-blanco) !important; }
    .block-container {
        max-width: 1380px;
        padding-top: 4.2rem;
        padding-bottom: 3rem;
    }
    .stMarkdown p { color: var(--gm-tinta); font-weight: 500; }

    /* ---------------- Barra lateral ---------------- */
    section[data-testid="stSidebar"] {
        background: var(--gm-carbon);
        border-right: 5px solid var(--gm-magenta);
    }
    section[data-testid="stSidebar"] * { color: var(--gm-blanco); }
    section[data-testid="stSidebar"] .block-container,
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1rem;
    }
    .gm-side-logo {
        display: block;
        width: 150px;
        margin: .2rem auto .4rem;
    }
    .gm-side-firma {
        text-align: center;
        font-size: .68rem;
        letter-spacing: .2em;
        text-transform: uppercase;
        color: var(--gm-magenta-claro) !important;
        font-weight: 800;
        margin-bottom: 1.1rem;
    }
    .gm-side-titulo {
        font-size: .7rem;
        font-weight: 900;
        letter-spacing: .18em;
        text-transform: uppercase;
        color: #CFC9CC !important;
        border-bottom: 2px solid var(--gm-grafito);
        padding-bottom: .4rem;
        margin: .8rem 0 .7rem;
    }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        justify-content: flex-start;
        text-align: left;
        min-height: 3.1rem;
        padding: .55rem .9rem;
        border-radius: 12px;
        font-weight: 800;
        font-size: .9rem;
        background: var(--gm-grafito);
        color: var(--gm-blanco);
        border: 2px solid #55504F;
        box-shadow: none;
        transition: transform .12s ease, border-color .12s ease,
                    background .12s ease;
    }
    section[data-testid="stSidebar"] .stButton > button p {
        color: var(--gm-blanco) !important;
        font-weight: 800;
        text-align: left;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: var(--gm-magenta);
        background: #4A4547;
        transform: translateX(3px);
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: var(--gm-magenta);
        border-color: var(--gm-blanco);
        box-shadow: 4px 4px 0 var(--gm-tinta);
    }
    .gm-side-nota {
        background: var(--gm-tinta);
        border-left: 4px solid var(--gm-magenta);
        border-radius: 10px;
        padding: .8rem .9rem;
        font-size: .78rem;
        line-height: 1.5;
        margin-top: 1.2rem;
    }
    .gm-side-nota b { color: var(--gm-magenta-claro) !important; }

    /* ---------------- Cabecera de modulo ---------------- */
    .gm-banner {
        position: relative;
        overflow: hidden;
        background: linear-gradient(115deg, var(--gm-tinta) 0%,
                                    var(--gm-carbon) 55%,
                                    var(--gm-magenta-oscuro) 100%);
        border: 3px solid var(--gm-tinta);
        border-radius: 22px;
        padding: 1.7rem 2rem;
        margin: 0 0 1.6rem;
        box-shadow: 7px 7px 0 var(--gm-magenta);
        color: var(--gm-blanco);
    }
    .gm-banner:after {
        content: "";
        position: absolute;
        right: -40px; bottom: -60px;
        width: 260px; height: 260px;
        background-image: radial-gradient(rgba(255,255,255,.22) 3px,
                                          transparent 3.5px);
        background-size: 26px 26px;
        transform: rotate(12deg);
    }
    .gm-banner-fila {
        display: flex; gap: 1.6rem; align-items: center;
        position: relative; z-index: 1; flex-wrap: wrap;
    }
    .gm-banner img { height: 74px; }
    .gm-banner .gm-sep {
        width: 4px; align-self: stretch; background: var(--gm-magenta);
        border-radius: 4px;
    }
    .gm-eyebrow {
        color: var(--gm-magenta-claro);
        font-size: .74rem; font-weight: 900; letter-spacing: .2em;
        text-transform: uppercase; margin-bottom: .3rem;
    }
    .gm-banner h1 {
        color: var(--gm-blanco) !important;
        font-size: clamp(1.6rem, 2.8vw, 2.4rem);
        font-weight: 900; letter-spacing: -.02em; line-height: 1.1;
        margin: 0; padding: 0;
    }
    .gm-banner p {
        color: #F1E9ED !important; margin: .5rem 0 0; font-weight: 500;
        max-width: 760px; line-height: 1.55;
    }
    .gm-chips { display: flex; gap: .5rem; flex-wrap: wrap;
                margin-top: .9rem; }
    .gm-banner .gm-chip {
        background: var(--gm-blanco); color: var(--gm-carbon);
        border-radius: 999px; padding: .25rem .8rem;
        font-size: .72rem; font-weight: 800; letter-spacing: .04em;
        text-transform: uppercase;
    }
    .gm-banner .gm-chip.m { background: var(--gm-magenta); color: var(--gm-blanco); }

    /* ---------------- Titulos de seccion ---------------- */
    .gm-seccion {
        display: flex; align-items: center; gap: .7rem;
        background: var(--gm-carbon); color: var(--gm-blanco);
        border-radius: 14px; padding: .65rem 1rem;
        margin: 1.6rem 0 1rem;
        box-shadow: 4px 4px 0 var(--gm-magenta);
    }
    .gm-seccion .gm-num {
        display: inline-flex; align-items: center; justify-content: center;
        min-width: 34px; height: 34px; border-radius: 50%;
        background: var(--gm-magenta); color: var(--gm-blanco);
        font-weight: 900; font-size: 1rem; border: 2px solid #fff;
    }
    .gm-seccion .gm-tit {
        font-weight: 900; text-transform: uppercase; letter-spacing: .1em;
        font-size: .9rem; color: var(--gm-blanco);
    }

    /* ---------------- Ayuda flotante (?) ---------------- */
    .gm-ayuda {
        position: relative; display: inline-flex; align-items: center;
        justify-content: center; width: 24px; height: 24px;
        border-radius: 50%; background: var(--gm-blanco);
        color: var(--gm-magenta) !important; font-weight: 900;
        font-size: .85rem; cursor: help; border: 2px solid var(--gm-magenta);
        margin-left: auto; flex: 0 0 24px; outline: none;
    }
    .gm-ayuda.claro { background: var(--gm-magenta);
                      color: var(--gm-blanco) !important;
                      border-color: var(--gm-carbon); margin-left: .4rem; }
    .gm-ayuda .gm-ayuda-texto {
        visibility: hidden; opacity: 0;
        position: absolute; top: 32px; right: -6px; z-index: 9999;
        width: min(380px, 80vw);
        background: var(--gm-tinta); color: var(--gm-blanco) !important;
        border: 2px solid var(--gm-magenta); border-radius: 12px;
        padding: .85rem 1rem; font-size: .8rem; font-weight: 500;
        line-height: 1.55; text-transform: none; letter-spacing: 0;
        text-align: left; box-shadow: 5px 5px 0 var(--gm-magenta);
        transition: opacity .12s ease;
    }
    .gm-ayuda.izq .gm-ayuda-texto { right: auto; left: -6px; }
    .gm-ayuda .gm-ayuda-texto b { color: var(--gm-magenta-claro); }
    .gm-ayuda:hover .gm-ayuda-texto,
    .gm-ayuda:focus .gm-ayuda-texto { visibility: visible; opacity: 1; }

    /* ---------------- Tarjetas ---------------- */
    .gm-tarjeta {
        background: var(--gm-blanco); color: var(--gm-tinta);
        border: 3px solid var(--gm-carbon); border-left: 10px solid
        var(--gm-magenta); border-radius: 16px; padding: 1.1rem 1.2rem;
        box-shadow: var(--gm-sombra); height: 100%;
    }
    .gm-tarjeta h3 {
        margin: 0 0 .35rem; font-size: 1.05rem; font-weight: 900;
        color: var(--gm-carbon); display: flex; align-items: center;
        gap: .5rem;
    }
    .gm-tarjeta p, .gm-tarjeta li { color: #2E2A2C; font-size: .86rem;
                                    line-height: 1.55; font-weight: 500; }
    .gm-tarjeta ol, .gm-tarjeta ul { margin: .3rem 0 0 1.1rem;
                                     padding: 0; }
    .gm-tarjeta .gm-etq {
        display: inline-block; background: var(--gm-carbon);
        color: var(--gm-blanco); font-size: .66rem; font-weight: 900;
        letter-spacing: .14em; text-transform: uppercase;
        padding: .2rem .55rem; border-radius: 6px; margin-bottom: .5rem;
    }
    .gm-tarjeta.oscura {
        background: var(--gm-carbon); color: var(--gm-blanco);
        border-color: var(--gm-tinta);
    }
    .gm-tarjeta.oscura h3 { color: var(--gm-blanco); }
    .gm-tarjeta.oscura .gm-etq { background: var(--gm-magenta); }
    .gm-muestra { display: inline-block; width: 26px; height: 26px;
                  border-radius: 7px; border: 3px solid var(--gm-carbon);
                  flex: 0 0 26px; }
    .gm-tarjeta.oscura p, .gm-tarjeta.oscura li { color: #EDE6EA; }

    .gm-carga {
        background: var(--gm-carbon); color: var(--gm-blanco);
        border-radius: 14px 14px 0 0; padding: .6rem .9rem;
        display: flex; align-items: center; gap: .5rem;
        font-weight: 800; font-size: .85rem; letter-spacing: .03em;
        border: 3px solid var(--gm-carbon); border-bottom: 0;
    }
    .gm-carga .gm-cod {
        background: var(--gm-magenta); border-radius: 6px;
        padding: .1rem .45rem; font-size: .72rem; font-weight: 900;
        letter-spacing: .08em;
    }
    .gm-carga small { color: #D9D1D5; font-weight: 600; }

    /* ---------------- Controles de Streamlit ---------------- */
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploaderDropzone"] {
        background: var(--gm-blanco);
        border: 3px dashed var(--gm-magenta);
        border-radius: 0 0 14px 14px;
        color: var(--gm-tinta);
    }
    [data-testid="stFileUploader"] section:hover,
    [data-testid="stFileUploaderDropzone"]:hover {
        background: var(--gm-rosa);
        border-color: var(--gm-carbon);
    }
    [data-testid="stFileUploader"] label p {
        font-weight: 800; color: var(--gm-carbon);
    }
    [data-testid="stFileUploader"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span {
        color: var(--gm-humo) !important;
    }
    [data-testid="stFileUploaderFile"] {
        background: var(--gm-rosa); border-radius: 10px;
        padding: .2rem .5rem; border: 2px solid var(--gm-carbon);
    }

    .stApp .stButton > button,
    .stApp .stDownloadButton > button {
        min-height: 2.9rem; border-radius: 12px; font-weight: 800;
        border: 3px solid var(--gm-carbon);
        background: var(--gm-blanco); color: var(--gm-carbon);
        box-shadow: 4px 4px 0 var(--gm-carbon);
        transition: transform .12s ease, box-shadow .12s ease;
    }
    .stApp .stButton > button p,
    .stApp .stDownloadButton > button p { font-weight: 800; }
    .stApp .stButton > button[kind="primary"],
    .stApp .stDownloadButton > button[kind="primary"],
    .stApp button[data-testid="stBaseButton-primary"] {
        background: var(--gm-magenta); color: var(--gm-blanco);
        border-color: var(--gm-carbon);
    }
    .stApp .stButton > button[kind="primary"] p,
    .stApp .stDownloadButton > button[kind="primary"] p {
        color: var(--gm-blanco) !important;
    }
    .stApp .stButton > button:hover:enabled,
    .stApp .stDownloadButton > button:hover:enabled {
        transform: translate(-2px, -2px);
        box-shadow: 6px 6px 0 var(--gm-carbon);
        border-color: var(--gm-carbon);
    }
    .stApp .stButton > button:disabled {
        background: #D8D2D5; color: #6B6568; box-shadow: none;
        border-color: #9C9598;
    }

    div[data-testid="stMetric"] {
        background: var(--gm-carbon); border: 3px solid var(--gm-tinta);
        border-top: 8px solid var(--gm-magenta);
        border-radius: 16px; padding: 1rem 1.1rem;
        box-shadow: 4px 4px 0 var(--gm-magenta);
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetricLabel"] p {
        color: var(--gm-magenta-claro) !important; font-weight: 800;
        text-transform: uppercase; letter-spacing: .06em;
        font-size: .74rem !important;
    }
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] div {
        color: var(--gm-blanco) !important; font-weight: 900;
    }

    [data-testid="stExpander"] {
        background: var(--gm-blanco);
        border: 3px solid var(--gm-carbon) !important;
        border-radius: 14px; box-shadow: 4px 4px 0 var(--gm-carbon);
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        background: var(--gm-rosa); font-weight: 800;
    }
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span { color: var(--gm-carbon);
                                              font-weight: 800; }

    .stApp input, .stApp textarea,
    .stApp [data-baseweb="select"] > div,
    .stApp [data-baseweb="input"] {
        border-radius: 10px !important;
        border-color: var(--gm-carbon) !important;
        background: var(--gm-blanco) !important;
        color: var(--gm-tinta) !important;
    }
    .stApp [data-baseweb="tag"] {
        background: var(--gm-magenta) !important;
    }
    .stApp [data-baseweb="tag"] span { color: var(--gm-blanco) !important; }
    .stApp [data-testid="stWidgetLabel"] p {
        color: var(--gm-carbon); font-weight: 800;
    }
    .stApp [data-testid="stRadio"] label p { font-weight: 700; }
    [data-testid="stTooltipIcon"] svg { color: var(--gm-magenta) !important;
                                        stroke: var(--gm-magenta); }

    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 3px solid var(--gm-carbon); border-radius: 12px;
        overflow: hidden; background: var(--gm-blanco);
    }
    [data-testid="stAlert"] {
        border-radius: 12px; border: 2px solid var(--gm-carbon);
        font-weight: 600;
    }
    [data-testid="stCaptionContainer"], .stCaption {
        color: var(--gm-humo) !important; font-weight: 600;
    }
    hr { border-color: var(--gm-carbon) !important; border-width: 2px; }

    /* Tabla de resultados DIAN */
    .gm-tabla { width: 100%; border-collapse: separate; border-spacing: 0;
                border: 3px solid var(--gm-carbon); border-radius: 14px;
                overflow: hidden; box-shadow: var(--gm-sombra);
                background: var(--gm-blanco); font-size: .85rem; }
    .gm-tabla th { background: var(--gm-carbon); color: var(--gm-blanco);
                   text-transform: uppercase; letter-spacing: .06em;
                   font-size: .7rem; padding: .7rem .6rem;
                   text-align: right; font-weight: 900; }
    .gm-tabla th:first-child, .gm-tabla td:first-child { text-align: left; }
    .gm-tabla td { padding: .6rem; border-top: 2px solid #E4DDE1;
                   text-align: right; color: var(--gm-tinta);
                   font-weight: 600; font-variant-numeric: tabular-nums; }
    .gm-tabla tr:nth-child(even) td { background: #FBF6F9; }
    .gm-estado { display: inline-block; padding: .2rem .65rem;
                 border-radius: 999px; font-size: .7rem; font-weight: 900;
                 letter-spacing: .06em; color: #fff; }
    .gm-estado.ok { background: var(--gm-verde); }
    .gm-estado.rev { background: var(--gm-rojo); }
    .gm-tabla td.gm-dif-cero { color: var(--gm-verde); font-weight: 900; }
    .gm-tabla td.gm-dif-no { color: var(--gm-rojo); font-weight: 900; }

    /* Visor de Excel/CSV con filas resaltadas */
    .gm-visor-xls { max-height: 640px; overflow: auto;
                    border: 3px solid var(--gm-carbon);
                    border-top: 0; border-radius: 0 0 12px 12px;
                    background: var(--gm-blanco); }
    .gm-visor-xls table { border-collapse: collapse; font-size: .74em;
                          width: max-content; min-width: 100%; }
    .gm-visor-xls th { background: #E7E3E5; color: var(--gm-carbon);
                       font-weight: 800; padding: .25rem .45rem;
                       border: 1px solid #CFC8CB; position: sticky;
                       top: 0; }
    .gm-visor-xls tbody th { position: sticky; left: 0; top: auto; }
    .gm-visor-xls td { padding: .25rem .45rem; border: 1px solid #E4DEE1;
                       color: var(--gm-tinta); white-space: nowrap;
                       max-width: 320px; overflow: hidden;
                       text-overflow: ellipsis; }
    .gm-visor-xls td.num { text-align: right;
                           font-variant-numeric: tabular-nums; }
    .gm-visor-xls tr.marcada td { background: var(--fondo); }
    .gm-visor-xls tr.marcada th { box-shadow: inset 5px 0 0 var(--borde); }
    .gm-visor-xls tr.actual td { font-weight: 800;
                                 border-top: 3px solid var(--gm-magenta);
                                 border-bottom: 3px solid var(--gm-magenta); }
    .gm-visor-xls tr.actual th { background: var(--gm-magenta);
                                 color: #fff; }
    .gm-visor-xls td.cotejo { text-align: center; }
    .gm-visor-xls td.cotejo span, .gm-cotejo {
        display: inline-block; min-width: 26px; padding: 1px 6px;
        border-radius: 6px; color: #fff !important; font-weight: 900;
        text-align: center; }
    .gm-leyenda { max-height: 340px; overflow: auto;
                  border: 3px solid var(--gm-carbon); border-radius: 12px;
                  background: var(--gm-blanco); }
    .gm-leyenda table { border-collapse: collapse; width: 100%;
                        font-size: .78rem; }
    .gm-leyenda th { background: var(--gm-carbon); color: #fff;
                     padding: .4rem .5rem; text-align: left;
                     position: sticky; top: 0; }
    .gm-leyenda td { padding: .4rem .5rem; border-top: 1px solid #E4DEE1;
                     vertical-align: top; color: var(--gm-tinta); }
    .gm-muestra-mini { display: inline-block; width: 16px; height: 16px;
                       border-radius: 4px; margin-left: 6px;
                       vertical-align: middle;
                       border: 1px solid rgba(0,0,0,.25); }
    .gm-zoom { overflow: auto; max-height: 82vh;
               border: 3px solid var(--gm-carbon); border-top: 0;
               border-radius: 0 0 12px 12px; background: #fff;
               margin-bottom: .6rem; }
    .gm-zoom img { display: block; max-width: none; }

    /* Explicacion al pasar el mouse sobre una partida marcada */
    .gm-lienzo { position: relative; }
    .gm-hot { position: absolute; cursor: help; border-radius: 3px; }
    .gm-hot:hover { outline: 3px solid var(--gm-magenta);
                    background: rgba(224, 17, 143, .10); z-index: 40; }
    .gm-tip { display: none; position: absolute; z-index: 60;
              top: calc(100% + 6px); left: 0;
              width: max-content; max-width: min(430px, 70vw);
              background: var(--gm-carbon); color: #FFFFFF !important;
              border-left: 5px solid var(--gm-magenta);
              border-radius: 8px; padding: .55rem .7rem;
              font-size: 12.5px; line-height: 1.38; font-weight: 500;
              white-space: normal; text-align: left;
              box-shadow: 0 8px 22px rgba(0, 0, 0, .35);
              pointer-events: none; }
    .gm-tip b { color: #FF7CC8; }
    .gm-tip i { color: #FFD24D; }
    .gm-hot:hover .gm-tip { display: block; }
    .gm-tip-arriba .gm-tip { top: auto; bottom: calc(100% + 6px); }
    .gm-tip-izq .gm-tip { left: auto; right: 0; }
    .gm-visor-xls td.gm-hot-td { position: relative; overflow: visible;
                                 cursor: help; }
    .gm-visor-xls td.gm-hot-td .gm-tip { left: calc(100% + 4px); top: -4px;
                                         font-size: 12.5px; }
    .gm-visor-xls tr:hover td.gm-hot-td .gm-tip { display: block; }
    .gm-visor-xls tr.marcada:hover td { outline: 1px solid var(--gm-magenta); }
    .gm-pagina-titulo { font-size: .78rem; font-weight: 800;
                        color: var(--gm-carbon); margin: .4rem 0 .2rem; }
    [data-testid="stImage"] img { border: 3px solid var(--gm-carbon);
                                  border-top: 0; border-radius: 0 0 12px 12px; }

    .gm-footer {
        margin-top: 3rem; background: var(--gm-carbon);
        color: var(--gm-blanco); border-radius: 16px;
        padding: 1rem 1.3rem; font-size: .78rem; line-height: 1.7;
        border-bottom: 6px solid var(--gm-magenta);
    }
    .gm-footer b { color: var(--gm-magenta-claro); letter-spacing: .12em; }

    /* ---------------- Barra superior (v6.8) ---------------- */
    /* El boton "Reportar un error" (o "Volver") va fijo en la franja
       oscura de arriba, separado del menu de modulos. El marcador
       .gm-marca-barra se oculta y el elemento siguiente (el boton) se fija. */
    [data-testid="stAppDeployButton"], [data-testid="stDeployButton"],
    .stDeployButton { display: none !important; }
    div[data-testid="stElementContainer"]:has(.gm-marca-barra),
    div.element-container:has(.gm-marca-barra) { display: none; }
    div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div[data-testid="stElementContainer"],
    div.element-container:has(.gm-marca-barra) + div.element-container {
        position: fixed; top: .62rem; right: 3.9rem; z-index: 1000002;
        width: auto !important;
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button,
    .stApp div.element-container:has(.gm-marca-barra)
        + div .stButton > button {
        min-height: 2.35rem; padding: .25rem 1rem; border-radius: 999px;
        background: transparent; color: var(--gm-blanco);
        border: 2px solid var(--gm-magenta-claro); box-shadow: none;
        font-size: .82rem; letter-spacing: .02em;
        display: inline-flex; align-items: center; gap: .4rem;
        white-space: nowrap;
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button p,
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button span,
    .stApp div.element-container:has(.gm-marca-barra)
        + div .stButton > button p {
        color: var(--gm-blanco) !important; font-size: .82rem;
        margin: 0;
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button:hover:enabled,
    .stApp div.element-container:has(.gm-marca-barra)
        + div .stButton > button:hover:enabled {
        background: var(--gm-magenta); border-color: var(--gm-blanco);
        transform: none; box-shadow: none;
    }

    /* Foco visible con teclado (accesibilidad) */
    .stApp button:focus-visible, .stApp a:focus-visible,
    .gm-ayuda:focus-visible {
        outline: 3px solid var(--gm-magenta) !important;
        outline-offset: 2px;
    }
    @media (max-width: 700px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        div[data-testid="stElementContainer"]:has(.gm-marca-barra)
            + div[data-testid="stElementContainer"],
        div.element-container:has(.gm-marca-barra) + div.element-container
            { right: 3.2rem; }
        .gm-banner { padding: 1.2rem; }
        .gm-banner img { height: 52px; }
        .gm-banner .gm-sep { display: none; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { transition: none !important; }
    }
    </style>
    """


def aplicar_estilos():
    """Inyecta la hoja de estilos de la marca GMYA. Se llama en cada
    ejecucion desde app.py."""
    st.markdown(CSS_GMYA, unsafe_allow_html=True)
