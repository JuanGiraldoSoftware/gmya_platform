"""Hoja de estilos de la marca GMYA (carbon #272526 + magenta #E0118F).
v6.15: tema oscuro en todo el tablero; encabezado de modulo de v6.11.
v6.12: sistema de diseno con tokens (--gm-m-*, --gm-n-*, estados,
radios, sombras), una sola tipografia (Inter) y superficies planas. Las
clases gm-* son las mismas y los nombres de variables antiguos quedan
como alias.

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Montserrat:wght@700;800&display=swap');

    /* componente invisible que bloquea la traduccion automatica */
    div[data-testid="stElementContainer"]:has(iframe[height="0"]),
    div.element-container:has(iframe[height="0"]) { display: none; }

    /* =====================================================================
       SISTEMA DE DISENO GMYA (v6.12)
       Marca: carbon #272526 + magenta #E0118F. El magenta se reserva para
       la accion principal, el estado activo y los acentos; las superficies
       son neutras y planas. Un solo tipo de letra (Inter), 4 pesos.
       Los nombres antiguos (--gm-tinta, --gm-degradado...) se conservan como
       alias para no romper estilos en linea de los modulos.
       ===================================================================== */
    :root {
        /* v6.15: TEMA OSCURO para todo el tablero. Los nombres de los tokens
           no cambian: n-0 es la superficie de las tarjetas, n-50 el fondo de
           la app y n-900 el texto principal (la escala va de oscuro a claro).
           Contraste del texto: n-900 15:1, n-700 11:1, n-500 6,6:1 sobre n-0. */
        /* Marca */
        --gm-m-50: rgba(224,17,143,.12);  --gm-m-100: rgba(224,17,143,.22);
        --gm-m-200: rgba(224,17,143,.36); --gm-m-500: #E0118F;
        --gm-m-600: #C20C7B; --gm-m-700: #A30A67;
        --gm-m-txt: #FF7CC8;   /* magenta para TEXTO sobre fondo oscuro */
        /* Neutros calidos (derivados del carbon de la marca) */
        --gm-n-0: #1F1C20;   --gm-n-25: #262227;  --gm-n-50: #151316;
        --gm-n-100: #2D292E; --gm-n-200: #39343B; --gm-n-300: #504A52;
        --gm-n-400: #8A8287; --gm-n-500: #A39BA0; --gm-n-600: #BDB5BA;
        --gm-n-700: #D3CCD0; --gm-n-800: #E6E0E3; --gm-n-900: #F4F0F2;
        --gm-n-950: #FFFFFF;
        /* Superficies mas oscuras que el fondo (barra lateral, paneles) */
        --gm-d-0: #19161A;   --gm-d-1: #1A171B;   --gm-d-borde: #2E2A30;
        --gm-flot: #2A262A;  --gm-flot-borde: #3D383D;
        /* Estados (claros, legibles sobre fondo oscuro) */
        --gm-ok: #4CC38A;    --gm-ok-bg: rgba(76,195,138,.14);
        --gm-alerta: #F0A44B; --gm-alerta-bg: rgba(240,164,75,.14);
        --gm-error: #F2736A; --gm-error-bg: rgba(242,115,106,.14);
        --gm-info: #8B95F5;  --gm-info-bg: rgba(139,149,245,.14);
        /* Tipografia, espacios, radios, sombras */
        --gm-fuente: 'Inter', 'Segoe UI', system-ui, -apple-system, Arial, sans-serif;
        --gm-r-sm: 6px; --gm-r-md: 8px; --gm-r-lg: 12px;
        --gm-sombra-xs: inset 0 1px 0 rgba(255,255,255,.035);
        --gm-sombra-sm: 0 1px 2px rgba(0,0,0,.4);
        --gm-sombra-flot: 0 16px 40px -8px rgba(0,0,0,.7);
        --gm-foco: 0 0 0 3px rgba(224,17,143,.35);

        /* Alias de versiones anteriores (usados en estilos en linea) */
        --gm-tinta: var(--gm-n-900); --gm-carbon: var(--gm-n-800);
        --gm-grafito: var(--gm-n-700); --gm-humo: var(--gm-n-500);
        --gm-magenta: var(--gm-m-500); --gm-magenta-oscuro: var(--gm-m-700);
        --gm-magenta-claro: #FF8AD0; --gm-rosa: var(--gm-m-50);
        --gm-rosa-2: var(--gm-m-100); --gm-papel: var(--gm-n-50);
        --gm-blanco: var(--gm-n-0); --gm-borde: var(--gm-n-200);
        --gm-verde: var(--gm-ok); --gm-rojo: var(--gm-error);
        --gm-radio: var(--gm-r-lg);
        --gm-sombra: var(--gm-sombra-sm); --gm-sombra-suave: var(--gm-sombra-xs);
        --gm-sombra-magenta: none; --gm-degradado: linear-gradient(135deg, #E0118F 0%, #B80C76 100%);
        color-scheme: dark;
    }

    html, body, .stApp, .stApp button, .stApp input, .stApp textarea,
    .stApp select, .stMarkdown, [data-testid="stMarkdownContainer"] {
        font-family: var(--gm-fuente);
        -webkit-font-smoothing: antialiased;
    }
    /* v6.17: fondo con profundidad (no negro plano): carbon calido con un
       brillo magenta muy tenue arriba a la derecha. */
    .stApp {
        background:
            radial-gradient(1100px 520px at 88% -8%, rgba(224,17,143,.09), transparent 62%),
            radial-gradient(900px 600px at -10% 110%, rgba(115,128,238,.05), transparent 60%),
            var(--gm-n-50);
        background-attachment: fixed;
        color: var(--gm-n-900);
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        font-family: var(--gm-fuente); letter-spacing: -.01em;
        color: var(--gm-n-900);
    }
    [data-testid="stHeader"] {
        background: rgba(21,19,22,.82);
        backdrop-filter: saturate(140%) blur(8px);
        border-bottom: 1px solid var(--gm-n-200);
    }
    .block-container { max-width: 1280px; padding-top: 4.75rem;
                       padding-bottom: 2.5rem; }
    .stMarkdown p { color: var(--gm-n-700); }

    /* ---------------- Barra lateral ---------------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1C181D 0%, #161317 100%);
        border-right: 1px solid var(--gm-d-borde);
    }
    section[data-testid="stSidebar"] * { color: #C9C1C6; }
    .gm-side-logo { display: block; width: 112px; margin: .25rem 0 .35rem .5rem; }
    .gm-side-firma {
        font-size: .72rem; line-height: 1.35; color: var(--gm-n-400) !important;
        font-weight: 500; margin: 0 0 1.25rem .5rem;
    }
    .gm-side-titulo {
        font-size: .69rem; font-weight: 600; letter-spacing: .08em;
        text-transform: uppercase; color: var(--gm-n-400) !important;
        margin: 1.1rem 0 .35rem .5rem;
    }
    section[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.stButton) {
        margin-bottom: -.55rem;
    }
    section[data-testid="stSidebar"] .stButton > button {
        width: 100%; justify-content: flex-start; text-align: left;
        min-height: 2.375rem; padding: .4rem .65rem; border-radius: var(--gm-r-md);
        background: transparent; border: 0; box-shadow: none;
        transition: background .12s ease, color .12s ease;
    }
    section[data-testid="stSidebar"] .stButton > button p {
        color: #C9C1C6 !important; font-weight: 500; font-size: .875rem;
        text-align: left;
    }
    section[data-testid="stSidebar"] .stButton > button [data-testid="stIconMaterial"],
    section[data-testid="stSidebar"] .stButton > button span {
        color: var(--gm-n-400) !important;
    }
    /* Nada dentro del boton lleva fondo ni sombra propios: el boton se
       sombrea como un todo. */
    section[data-testid="stSidebar"] .stButton > button * {
        background: transparent !important; box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button {
        border: 1px solid transparent !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,.05) !important;
        border-color: rgba(255,255,255,.06) !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover p { color: #FFFFFF !important; }
    /* Modulo actual: un solo sombreado sutil en todo el boton. */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(90deg, rgba(224,17,143,.16), rgba(224,17,143,.06)) !important;
        border: 1px solid rgba(224,17,143,.30) !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] p,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p {
        color: #FFFFFF !important; font-weight: 600;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] span,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span {
        color: var(--gm-magenta-claro) !important;
    }
    .gm-side-nota {
        border-top: 1px solid rgba(255,255,255,.08); padding: .9rem .5rem 0;
        font-size: .75rem; line-height: 1.55; margin-top: 1.25rem;
        color: var(--gm-n-400) !important;
    }
    .gm-side-nota b { color: #E6E0E3 !important; font-weight: 600; }

    /* ---------------- Encabezado de pagina (diseno v6.11) ---------------- */
    .gm-banner {
        position: relative; overflow: hidden;
        background: linear-gradient(120deg, #1B191A 0%, #2E2A2C 52%, #8E0A5B 100%);
        border: 1px solid rgba(255,255,255,.06);
        border-radius: 20px; padding: 1.6rem 1.9rem; margin: 0 0 1rem;
        box-shadow: 0 18px 40px -22px rgba(142,10,91,.65);
        color: #FFFFFF;
    }
    .gm-banner:after {
        content: ""; position: absolute; right: -80px; top: -80px;
        width: 320px; height: 320px; border-radius: 50%; pointer-events: none;
        background: radial-gradient(circle, rgba(255,138,208,.35), transparent 65%);
    }
    .gm-banner-fila {
        display: flex; gap: 1.4rem; align-items: center;
        position: relative; z-index: 1; flex-wrap: wrap;
    }
    .gm-banner img { height: 62px; opacity: .95; }
    .gm-banner .gm-sep {
        width: 1px; align-self: stretch; background: rgba(255,255,255,.18);
    }
    .gm-eyebrow {
        color: var(--gm-magenta-claro); font-size: .7rem; font-weight: 800;
        letter-spacing: .2em; text-transform: uppercase; margin-bottom: .35rem;
        font-family: 'Montserrat', var(--gm-fuente);
    }
    .gm-banner h1 {
        color: #FFFFFF !important; font-family: 'Montserrat', var(--gm-fuente) !important;
        font-size: clamp(1.5rem, 2.6vw, 2.15rem); font-weight: 800;
        letter-spacing: -.02em; line-height: 1.12; margin: 0; padding: 0;
    }
    .gm-banner p {
        color: #EDE6EA !important; margin: .5rem 0 0; font-weight: 400;
        max-width: 760px; line-height: 1.6; font-size: .95rem;
    }
    .gm-chips { display: flex; gap: .45rem; flex-wrap: wrap; margin-top: .9rem; }
    .gm-chip {
        background: var(--gm-n-100); color: var(--gm-n-700);
        border: 1px solid var(--gm-n-200); border-radius: 999px;
        padding: .125rem .625rem; font-size: .75rem; font-weight: 500;
    }
    .gm-chip.m { background: var(--gm-m-50); color: var(--gm-m-txt);
                 border-color: var(--gm-m-100); }
    .gm-banner .gm-chip {
        background: rgba(255,255,255,.1); color: #FFFFFF;
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 999px; padding: .22rem .75rem;
        font-size: .72rem; font-weight: 600; letter-spacing: .02em;
    }
    .gm-banner .gm-chip.m { background: var(--gm-degradado); border-color: transparent; }

    /* ---------------- Titulos de seccion ---------------- */
    .gm-seccion {
        display: flex; align-items: center; gap: .625rem;
        margin: 1.25rem 0 .25rem;
    }
    .gm-seccion .gm-num {
        display: inline-flex; align-items: center; justify-content: center;
        width: 1.5rem; height: 1.5rem; border-radius: 999px;
        background: var(--gm-m-100); color: var(--gm-magenta-claro);
        font-weight: 600; font-size: .75rem; flex: 0 0 1.5rem;
        font-variant-numeric: tabular-nums;
    }
    .gm-seccion .gm-tit {
        font-weight: 600; font-size: 1.125rem; color: var(--gm-n-900);
        letter-spacing: -.01em;
    }
    .gm-seccion::after {
        content: ""; flex: 1; height: 1px; background: var(--gm-n-200);
        margin-left: .5rem; order: 3;
    }
    .gm-seccion .gm-ayuda { order: 2; margin-left: 0; }

    /* ---------------- Ayuda (?) ---------------- */
    .gm-ayuda {
        position: relative; display: inline-flex; align-items: center;
        justify-content: center; width: 18px; height: 18px; flex: 0 0 18px;
        border-radius: 50%; background: transparent;
        color: var(--gm-n-500) !important; font-weight: 600; font-size: .6875rem;
        cursor: help; border: 1px solid var(--gm-n-300); margin-left: .25rem;
        outline: none; transition: color .12s, border-color .12s;
    }
    .gm-ayuda:hover, .gm-ayuda:focus-visible {
        color: var(--gm-m-txt) !important; border-color: var(--gm-m-500);
    }
    .gm-ayuda.claro { color: var(--gm-n-500) !important; }
    .gm-ayuda .gm-ayuda-texto {
        display: none;
        position: absolute; top: 26px; left: -6px; z-index: 9999;
        width: min(360px, 80vw);
        background: var(--gm-flot); color: #fff !important;
        border: 1px solid var(--gm-flot-borde);
        border-radius: var(--gm-r-md); padding: .75rem .875rem;
        font-size: .8125rem; font-weight: 400; line-height: 1.55;
        text-transform: none; letter-spacing: 0; text-align: left;
        box-shadow: var(--gm-sombra-flot); transition: opacity .12s ease;
    }
    .gm-ayuda.izq .gm-ayuda-texto { left: auto; right: -6px; }
    .gm-ayuda .gm-ayuda-texto b { color: var(--gm-magenta-claro); font-weight: 600; }
    /* display (no visibility): oculto no ocupa espacio ni crea scroll
       horizontal cerca del borde derecho. */
    .gm-ayuda:hover .gm-ayuda-texto,
    .gm-ayuda:focus .gm-ayuda-texto { display: block; }

    /* ---------------- Tarjetas ---------------- */
    .gm-tarjeta {
        background: var(--gm-n-0); color: var(--gm-n-900);
        border: 1px solid var(--gm-n-200); border-radius: var(--gm-r-lg);
        padding: 1.125rem 1.25rem; box-shadow: var(--gm-sombra-xs);
        height: 100%; position: relative;
    }
    .gm-tarjeta h3 {
        margin: 0 0 .375rem; font-size: 1rem; font-weight: 600;
        color: var(--gm-n-900); display: flex; align-items: center; gap: .5rem;
        line-height: 1.35;
    }
    .gm-tarjeta p, .gm-tarjeta li { color: var(--gm-n-600); font-size: .875rem;
                                    line-height: 1.55; margin: 0; }
    .gm-tarjeta ol, .gm-tarjeta ul { margin: .4rem 0 0 1.1rem; padding: 0; }
    .gm-tarjeta .gm-etq {
        display: inline-block; color: var(--gm-n-500); font-size: .75rem;
        font-weight: 500; margin-bottom: .375rem;
    }
    /* "oscura" (version anterior): ahora solo un acento, sin bloque negro */
    .gm-tarjeta.oscura { box-shadow: inset 0 3px 0 var(--gm-m-500), var(--gm-sombra-xs); }
    /* Inicio: la tarjeta y su boton forman una sola pieza (el boton es el
       pie de la tarjeta). */
    .gm-tarjeta.inicio { min-height: 8.5rem; border-bottom: 0;
                         border-radius: var(--gm-r-lg) var(--gm-r-lg) 0 0;
                         box-shadow: none; }
    div[data-testid="stElementContainer"]:has(.gm-tarjeta.inicio) {
        margin-bottom: -1rem; }
    div[data-testid="stElementContainer"]:has(.gm-tarjeta.inicio)
        + div[data-testid="stElementContainer"] .stButton > button {
        border-radius: 0 0 var(--gm-r-lg) var(--gm-r-lg);
        border-color: var(--gm-n-200); background: var(--gm-n-25);
        justify-content: flex-start; padding-left: 1.25rem; box-shadow: none;
    }
    div[data-testid="stElementContainer"]:has(.gm-tarjeta.inicio)
        + div[data-testid="stElementContainer"] .stButton > button p {
        color: var(--gm-m-txt) !important; }
    div[data-testid="stElementContainer"]:has(.gm-tarjeta.inicio)
        + div[data-testid="stElementContainer"] .stButton > button:hover:enabled {
        background: var(--gm-m-50); border-color: var(--gm-m-200); }
    div[data-testid="stElementContainer"]:has(.gm-tarjeta.inicio)
        + div[data-testid="stElementContainer"] .stButton > button:hover:enabled p {
        color: #FFFFFF !important; }
    .gm-muestra { display: inline-block; width: 14px; height: 14px;
                  border-radius: 4px; border: 1px solid rgba(255,255,255,.25);
                  flex: 0 0 14px; }

    /* Encabezado de una carga de archivo: forma una sola pieza con la zona
       de arrastre que va debajo. */
    .gm-carga {
        background: var(--gm-n-0); color: var(--gm-n-900);
        border: 1px solid var(--gm-n-200); border-bottom: 0;
        border-radius: var(--gm-r-lg) var(--gm-r-lg) 0 0;
        padding: .75rem .875rem; display: flex; align-items: center; gap: .625rem;
        font-weight: 600; font-size: .875rem; line-height: 1.35;
    }
    /* La cabecera y la zona de arrastre quedan pegadas (sin el espacio
       que Streamlit pone entre elementos). */
    div[data-testid="stElementContainer"]:has(> div .gm-carga),
    div[data-testid="stElementContainer"]:has(.gm-carga) { margin-bottom: -1rem; }
    .gm-carga .gm-cod {
        background: var(--gm-n-100); color: var(--gm-n-700);
        border-radius: var(--gm-r-sm); padding: .125rem .4rem;
        font-size: .6875rem; font-weight: 600; letter-spacing: .03em;
        font-variant-numeric: tabular-nums; flex: 0 0 auto;
    }
    .gm-carga small { color: var(--gm-n-500); font-weight: 400; font-size: .75rem; }
    .gm-carga .gm-ayuda { margin-left: auto; }

    /* ---------------- Controles de Streamlit ---------------- */
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploader"] section {
        background: var(--gm-n-0); border: 1px dashed var(--gm-n-300);
        border-radius: 0 0 var(--gm-r-lg) var(--gm-r-lg); color: var(--gm-n-700);
        transition: border-color .12s, background .12s;
    }
    [data-testid="stFileUploaderDropzone"]:hover,
    [data-testid="stFileUploader"] section:hover {
        border-color: var(--gm-m-500); background: var(--gm-m-50);
    }
    [data-testid="stFileUploader"] label p { font-weight: 600; color: var(--gm-n-800); }
    [data-testid="stFileUploaderDropzoneInstructions"] span,
    [data-testid="stFileUploader"] small { color: var(--gm-n-500) !important; }
    [data-testid="stFileUploaderFile"] {
        background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-md);
    }

    .stApp .stButton > button,
    .stApp .stDownloadButton > button,
    .stApp .stFormSubmitButton > button,
    .stApp button[data-testid="stBaseButton-secondary"] {
        min-height: 2.5rem; border-radius: var(--gm-r-md);
        font-weight: 600; font-size: .875rem;
        border: 1px solid var(--gm-n-300); background: var(--gm-n-25);
        color: var(--gm-n-900); box-shadow: none;
        transition: background .12s, border-color .12s, color .12s;
    }
    .stApp .stButton > button p, .stApp .stDownloadButton > button p,
    .stApp .stFormSubmitButton > button p,
    .stApp button[data-testid="stBaseButton-secondary"] p {
        font-weight: 600; font-size: .875rem; color: var(--gm-n-900) !important;
    }
    .stApp .stButton > button:hover:enabled,
    .stApp .stDownloadButton > button:hover:enabled,
    .stApp .stFormSubmitButton > button:hover:enabled,
    .stApp button[data-testid="stBaseButton-secondary"]:hover:enabled {
        border-color: var(--gm-m-500); background: #2E2A2E; color: #FFFFFF;
    }
    .stApp .stButton > button:hover:enabled *,
    .stApp .stDownloadButton > button:hover:enabled *,
    .stApp .stFormSubmitButton > button:hover:enabled *,
    .stApp button[data-testid="stBaseButton-secondary"]:hover:enabled * {
        color: #FFFFFF !important;
    }
    .stApp .stButton > button:active:enabled,
    .stApp .stDownloadButton > button:active:enabled { background: #383338; }
    .stApp .stButton > button[kind="primary"],
    .stApp .stDownloadButton > button[kind="primary"],
    .stApp .stFormSubmitButton > button[kind="primary"],
    .stApp button[data-testid="stBaseButton-primary"] {
        background: var(--gm-m-600); border-color: var(--gm-m-600);
        color: #fff;
    }
    .stApp .stButton > button[kind="primary"] *,
    .stApp .stDownloadButton > button[kind="primary"] *,
    .stApp button[data-testid="stBaseButton-primary"] * { color: #fff !important; }
    .stApp .stButton > button[kind="primary"]:hover:enabled,
    .stApp .stDownloadButton > button[kind="primary"]:hover:enabled,
    .stApp button[data-testid="stBaseButton-primary"]:hover:enabled {
        background: #D90F89; border-color: #D90F89; color: #fff;
    }
    /* Botones de texto (tertiary / minimal / borrar archivo...) */
    .stApp button[data-testid="stBaseButton-tertiary"],
    .stApp button[data-testid="stBaseButton-minimal"],
    .stApp button[data-testid="stBaseButton-borderlessIcon"] {
        color: var(--gm-n-700); background: transparent;
    }
    .stApp button[data-testid="stBaseButton-tertiary"]:hover,
    .stApp button[data-testid="stBaseButton-minimal"]:hover,
    .stApp button[data-testid="stBaseButton-borderlessIcon"]:hover {
        color: #FFFFFF; background: rgba(255,255,255,.08);
    }
    .stApp button[data-testid="stBaseButton-tertiary"]:hover *,
    .stApp button[data-testid="stBaseButton-minimal"]:hover * { color: #FFFFFF !important; }
    .stApp .stButton > button:disabled,
    .stApp .stDownloadButton > button:disabled,
    .stApp button[data-testid^="stBaseButton"]:disabled {
        background: var(--gm-n-100); color: var(--gm-n-400);
        border-color: var(--gm-n-200); box-shadow: none;
    }
    .stApp .stButton > button:disabled *,
    .stApp button[data-testid^="stBaseButton"]:disabled * { color: var(--gm-n-400) !important; }

    div[data-testid="stMetric"] {
        background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-lg); padding: .875rem 1rem;
        box-shadow: var(--gm-sombra-xs);
    }
    div[data-testid="stMetric"] label,
    div[data-testid="stMetricLabel"] p {
        color: var(--gm-n-500) !important; font-weight: 500;
        font-size: .8125rem !important;
    }
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] div {
        color: var(--gm-n-900) !important; font-weight: 600;
        font-size: 1.5rem !important; line-height: 1.25;
        font-variant-numeric: tabular-nums; letter-spacing: -.01em;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    div[data-testid="stMetricDelta"] { font-size: .8125rem; }

    [data-testid="stExpander"] details, [data-testid="stExpander"] {
        background: var(--gm-n-0); border-color: var(--gm-n-200) !important;
        border-radius: var(--gm-r-lg);
    }
    [data-testid="stExpander"] summary:hover { background: var(--gm-n-25); }
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span { color: var(--gm-n-800); font-weight: 600;
                                              font-size: .9rem; }

    .stApp input, .stApp textarea,
    .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="input"] {
        border-radius: var(--gm-r-md) !important;
        border-color: var(--gm-n-300) !important;
        background: var(--gm-n-0) !important; color: var(--gm-n-900) !important;
    }
    .stApp [data-baseweb="input"]:focus-within,
    .stApp [data-baseweb="select"] > div:focus-within,
    .stApp textarea:focus {
        border-color: var(--gm-m-500) !important; box-shadow: var(--gm-foco) !important;
    }
    .stApp [data-baseweb="tag"] { background: var(--gm-m-50) !important;
                                  border: 1px solid var(--gm-m-100); }
    .stApp [data-baseweb="tag"] span { color: var(--gm-m-txt) !important; }
    .stApp [data-testid="stWidgetLabel"] p {
        color: var(--gm-n-800); font-weight: 500; font-size: .875rem;
    }
    [data-testid="stTooltipIcon"] svg { color: var(--gm-n-400) !important;
                                        stroke: var(--gm-n-400); }

    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border: 1px solid var(--gm-n-200); border-radius: var(--gm-r-lg);
        overflow: hidden; background: var(--gm-n-0);
    }
    [data-testid="stAlert"] > div, [data-testid="stAlertContainer"] {
        border-radius: var(--gm-r-md);
    }
    [data-testid="stCaptionContainer"], .stCaption {
        color: var(--gm-n-500) !important; font-size: .8125rem;
    }
    hr { border-color: var(--gm-n-200) !important; }
    .stApp [data-testid="stTabs"] button[aria-selected="true"] p {
        color: var(--gm-m-txt) !important; font-weight: 600;
    }
    .stApp [data-testid="stTabs"] button:hover p { color: #FFFFFF !important; }

    /* Tabla de resultados DIAN (con desplazamiento propio si no cabe) */
    .gm-tabla-cont { overflow-x: auto; border-radius: var(--gm-r-lg); }
    .gm-tabla-cont .gm-tabla { min-width: 720px; }
    .gm-tabla { width: 100%; border-collapse: separate; border-spacing: 0;
                border: 1px solid var(--gm-borde); border-radius: var(--gm-r-lg);
                overflow: hidden; box-shadow: var(--gm-sombra-suave);
                background: var(--gm-blanco); font-size: .85rem; }
    .gm-tabla th { background: var(--gm-n-50); color: var(--gm-n-600);
                   border-bottom: 1px solid var(--gm-borde);
                   font-size: .75rem; padding: .7rem .6rem;
                   text-align: right; font-weight: 700; }
    .gm-tabla th:first-child, .gm-tabla td:first-child { text-align: left; }
    .gm-tabla td { padding: .6rem; border-top: 1px solid var(--gm-borde);
                   text-align: right; color: var(--gm-tinta);
                   font-weight: 600; font-variant-numeric: tabular-nums; }
    .gm-tabla tr:nth-child(even) td { background: var(--gm-n-25); }
    .gm-estado { display: inline-block; padding: .2rem .65rem;
                 border-radius: 999px; font-size: .7rem; font-weight: 700;
                 letter-spacing: .06em; color: #fff; }
    .gm-estado.ok { background: var(--gm-ok-bg); color: var(--gm-ok); }
    .gm-estado.rev { background: var(--gm-error-bg); color: var(--gm-error); }
    .gm-tabla td.gm-dif-cero { color: var(--gm-verde); font-weight: 700; }
    .gm-tabla td.gm-dif-no { color: var(--gm-rojo); font-weight: 700; }

    /* Visor de Excel/CSV con filas resaltadas */
    .gm-visor-xls { max-height: 640px; overflow: auto;
                    border: 1px solid var(--gm-borde);
                    border-top: 0; border-radius: 0 0 var(--gm-r-lg) var(--gm-r-lg);
                    background: #FFFFFF; color: #1C1A1C; }
    .gm-visor-xls table { border-collapse: collapse; font-size: .74em;
                          width: max-content; min-width: 100%; }
    .gm-visor-xls th { background: #E7E3E5; color: #272526;
                       font-weight: 600; padding: .25rem .45rem;
                       border: 1px solid #CFC8CB; position: sticky;
                       top: 0; }
    .gm-visor-xls tbody th { position: sticky; left: 0; top: auto; }
    .gm-visor-xls td { padding: .25rem .45rem; border: 1px solid #E4DEE1;
                       color: #1C1A1C; white-space: nowrap;
                       max-width: 320px; overflow: hidden;
                       text-overflow: ellipsis; }
    .gm-visor-xls td.num { text-align: right;
                           font-variant-numeric: tabular-nums; }
    .gm-visor-xls tr.marcada td { background: var(--fondo); }
    .gm-visor-xls tr.marcada th { box-shadow: inset 5px 0 0 var(--borde); }
    .gm-visor-xls tr.actual td { font-weight: 600;
                                 border-top: 2px solid var(--gm-magenta);
                                 border-bottom: 2px solid var(--gm-magenta); }
    .gm-visor-xls tr.actual th { background: var(--gm-magenta);
                                 color: #fff; }
    .gm-visor-xls td.cotejo { text-align: center; }
    .gm-visor-xls td.cotejo span, .gm-cotejo {
        display: inline-block; min-width: 26px; padding: 1px 6px;
        border-radius: 6px; color: #fff !important; font-weight: 700;
        text-align: center; }
    .gm-leyenda { max-height: 340px; overflow: auto;
                  border: 1px solid var(--gm-borde); border-radius: var(--gm-r-lg);
                  background: var(--gm-blanco); }
    .gm-leyenda table { border-collapse: collapse; width: 100%;
                        font-size: .78rem; }
    .gm-leyenda th { background: var(--gm-n-50); color: var(--gm-n-600);
                     font-weight: 600; border-bottom: 1px solid var(--gm-borde);
                     padding: .4rem .5rem; text-align: left;
                     position: sticky; top: 0; }
    .gm-leyenda td { padding: .4rem .5rem; border-top: 1px solid var(--gm-n-200);
                     vertical-align: top; color: var(--gm-tinta); }
    .gm-muestra-mini { display: inline-block; width: 16px; height: 16px;
                       border-radius: 4px; margin-left: 6px;
                       vertical-align: middle;
                       border: 1px solid rgba(0,0,0,.25); }
    .gm-zoom { overflow: auto; max-height: 82vh;
               border: 1px solid var(--gm-borde); border-top: 0;
               border-radius: 0 0 var(--gm-r-lg) var(--gm-r-lg); background: #fff;
               margin-bottom: .6rem; }
    .gm-zoom img { display: block; max-width: none; }

    /* Explicacion al pasar el mouse sobre una partida marcada */
    .gm-lienzo { position: relative; }
    .gm-hot { position: absolute; cursor: help; border-radius: 3px; }
    .gm-hot:hover { outline: 2px solid var(--gm-magenta);
                    background: rgba(224, 17, 143, .10); z-index: 40; }
    .gm-tip { display: none; position: absolute; z-index: 60;
              top: calc(100% + 6px); left: 0;
              width: max-content; max-width: min(430px, 70vw);
              background: var(--gm-flot); color: #FFFFFF !important;
              border-left: 3px solid var(--gm-magenta);
              border-radius: 8px; padding: .55rem .7rem;
              font-size: 12.5px; line-height: 1.38; font-weight: 500;
              white-space: normal; text-align: left;
              box-shadow: var(--gm-sombra-flot);
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
    .gm-pagina-titulo { font-size: .78rem; font-weight: 600;
                        color: var(--gm-carbon); margin: .4rem 0 .2rem; }
    [data-testid="stImage"] img { border: 1px solid var(--gm-borde);
                                  border-top: 0; border-radius: 0 0 var(--gm-r-lg) var(--gm-r-lg); }


    .gm-footer {
        margin-top: 3rem; background: transparent;
        color: var(--gm-humo); border-top: 1px solid var(--gm-borde);
        padding: 1rem .2rem; font-size: .76rem; line-height: 1.7;
    }
    .gm-footer b { color: var(--gm-magenta); letter-spacing: .12em; }



    .gm-footer {
        margin-top: 3rem; color: var(--gm-n-500);
        border-top: 1px solid var(--gm-n-200);
        padding: 1rem 0; font-size: .75rem; line-height: 1.7;
    }
    .gm-footer b { color: var(--gm-n-800); font-weight: 600; }

    /* ---------------- Barra superior ---------------- */
    /* El boton "Reportar un error" (o "Volver") va fijo en la franja de
       arriba, separado del menu. El marcador .gm-marca-barra se oculta y el
       elemento siguiente (el boton) se fija. */
    [data-testid="stAppDeployButton"], [data-testid="stDeployButton"],
    .stDeployButton { display: none !important; }
    div[data-testid="stElementContainer"]:has(.gm-marca-barra),
    div.element-container:has(.gm-marca-barra) { display: none; }
    div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div[data-testid="stElementContainer"],
    div.element-container:has(.gm-marca-barra) + div.element-container {
        position: fixed; top: .7rem; right: 3.75rem; z-index: 1000002;
        width: auto !important;
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button,
    .stApp div.element-container:has(.gm-marca-barra)
        + div .stButton > button {
        min-height: 2.125rem; padding: .2rem .75rem; border-radius: var(--gm-r-md);
        background: var(--gm-n-0); color: var(--gm-n-800);
        border: 1px solid var(--gm-n-300); box-shadow: none;
        white-space: nowrap;
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button p,
    .stApp div.element-container:has(.gm-marca-barra)
        + div .stButton > button p {
        color: var(--gm-n-800) !important; font-size: .8125rem; margin: 0;
        font-weight: 500;
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button:hover:enabled {
        border-color: var(--gm-m-500); background: var(--gm-m-100);
    }
    .stApp div[data-testid="stElementContainer"]:has(.gm-marca-barra)
        + div .stButton > button:hover:enabled p { color: #FFFFFF !important; }

    /* Foco visible con teclado (accesibilidad) */
    .stApp button:focus-visible, .stApp a:focus-visible,
    .gm-ayuda:focus-visible, .gm-emp-off:focus-visible {
        outline: 2px solid var(--gm-m-500) !important; outline-offset: 2px;
    }

    /* Inicio */
    .gm-novedad {
        background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-md); padding: .625rem .875rem;
        font-size: .8125rem; line-height: 1.55; color: var(--gm-n-600);
        display: flex; gap: .5rem; align-items: baseline;
    }
    .gm-novedad b { color: var(--gm-n-900); font-weight: 600; }
    .gm-novedad .gm-pill {
        background: var(--gm-m-50); color: var(--gm-m-txt);
        border-radius: 999px; padding: .05rem .5rem; font-size: .6875rem;
        font-weight: 600; white-space: nowrap;
    }

    /* Programacion de pagos: empresas no implementadas y glosario */
    .gm-emp-off {
        position: relative; display: flex; align-items: center; gap: .5rem;
        min-height: 2.5rem; padding: .4rem .75rem; margin-bottom: 0;
        border-radius: var(--gm-r-md); border: 1px dashed var(--gm-n-300);
        background: transparent; color: var(--gm-n-400) !important;
        font-size: .875rem; font-weight: 500; cursor: not-allowed; outline: none;
    }
    .gm-emp-off .gm-emp-nombre { flex: 1; overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap; }
    .gm-emp-off .gm-emp-candado {
        display: inline-flex; align-items: center; justify-content: center;
        min-width: 0; height: auto; padding: .05rem .4rem; flex: 0 0 auto;
        border-radius: 999px; border: 0; background: var(--gm-n-100);
        color: var(--gm-n-500); font-size: .6875rem; font-weight: 500;
    }
    .gm-emp-off .gm-ayuda-texto {
        display: none; position: absolute; top: calc(100% + 6px);
        left: 0; z-index: 9999; width: min(320px, 80vw);
        background: var(--gm-flot); color: #fff !important;
        border: 1px solid var(--gm-flot-borde);
        border-radius: var(--gm-r-md); padding: .75rem .875rem;
        font-size: .8125rem; font-weight: 400; line-height: 1.5;
        box-shadow: var(--gm-sombra-flot); white-space: normal; cursor: default;
    }
    .gm-emp-off .gm-ayuda-texto b { color: var(--gm-magenta-claro); }
    .gm-emp-off:hover .gm-ayuda-texto,
    .gm-emp-off:focus .gm-ayuda-texto { display: block; }
    .gm-glosario { display: flex; flex-wrap: wrap; align-items: center;
        gap: .375rem; margin: .25rem 0 .75rem; }
    .gm-glo-tit { font-size: .75rem; font-weight: 500; color: var(--gm-n-500);
        margin-right: .25rem; }
    .gm-glo-chip { display: inline-flex; align-items: center; gap: .3rem;
        background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: 999px; padding: .125rem .3rem .125rem .625rem;
        font-size: .75rem; font-weight: 500; color: var(--gm-n-700); }
    .gm-glo-chip .gm-ayuda { margin-left: 0; width: 16px; height: 16px;
        flex: 0 0 16px; font-size: .625rem; }


    /* =====================================================================
       v6.13 · Componentes visuales (gmya/ui/visual.py)
       Base clara + bloques de resumen oscuros (dona, datos clave).
       ===================================================================== */
    .gm-ico-svg { display: block; flex: 0 0 auto; }
    .t-magenta { background: var(--gm-m-50); color: var(--gm-m-txt); }
    .t-indigo  { background: rgba(139,149,245,.14); color: #A5ADFF; }
    .t-teal    { background: rgba(45,190,180,.14);  color: #5FD3CB; }
    .t-ambar   { background: rgba(240,164,75,.14);  color: #F5B567; }
    .t-verde   { background: rgba(76,195,138,.14);  color: #6FD6A2; }
    .t-pizarra { background: rgba(160,174,192,.14); color: #B8C2CF; }
    .t-carbon  { background: var(--gm-n-100); color: #fff; }

    /* Indicadores */
    .gm-kpis { display: grid; gap: .75rem; margin: .25rem 0;
        grid-template-columns: repeat(var(--gm-cols, 4), minmax(0, 1fr)); }
    .gm-kpi { background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-lg); padding: .875rem 1rem .9rem;
        box-shadow: var(--gm-sombra-xs); min-width: 0; }
    .gm-kpi-cab { display: flex; align-items: center; gap: .5rem;
        margin-bottom: .5rem; min-width: 0; }
    .gm-kpi-ico { display: inline-flex; align-items: center;
        justify-content: center; width: 2rem; height: 2rem; flex: 0 0 2rem;
        border-radius: var(--gm-r-md); }
    .gm-kpi-et { font-size: .8125rem; font-weight: 500; color: var(--gm-n-500);
        flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
        white-space: nowrap; }
    .gm-kpi-val { font-size: 1.5rem; font-weight: 700; line-height: 1.2;
        color: var(--gm-n-900); letter-spacing: -.02em;
        font-variant-numeric: tabular-nums; white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis; }
    .gm-kpi-det { font-size: .78rem; color: var(--gm-n-500); margin-top: .2rem;
        font-variant-numeric: tabular-nums; }
    .gm-insignia { display: inline-flex; align-items: center; gap: .25rem;
        font-size: .6875rem; font-weight: 600; padding: .1rem .45rem .1rem .35rem;
        border-radius: 999px; white-space: nowrap; flex: 0 0 auto; }
    .gm-insignia.ok { background: var(--gm-ok-bg); color: var(--gm-ok); }
    .gm-insignia.alerta { background: var(--gm-alerta-bg); color: var(--gm-alerta); }
    .gm-insignia.error { background: var(--gm-error-bg); color: var(--gm-error); }

    /* Panel de resumen oscuro (dona) */
    .gm-panel { background: linear-gradient(160deg, #1D1A1D 0%, #141214 70%);
        color: #fff; border: 1px solid var(--gm-d-borde);
        border-radius: var(--gm-r-lg); padding: 1.125rem 1.25rem 1.25rem;
        box-shadow: 0 1px 0 rgba(255,255,255,.04) inset;
        margin: .25rem 0 .5rem; }
    .gm-panel-tit { font-weight: 600; font-size: 1rem; color: #fff; }
    .gm-panel-sub { font-size: .8125rem; color: var(--gm-n-400); margin-top: .1rem; }
    .gm-panel-cuerpo { display: flex; align-items: center; gap: 2rem;
        margin-top: 1rem; flex-wrap: wrap; }
    .gm-dona { position: relative; flex: 0 0 auto; }
    .gm-dona svg { display: block; }
    .gm-dona circle { transition: stroke-width .12s; }
    .gm-dona circle:hover { stroke-width: 22; }
    .gm-dona-centro { position: absolute; inset: 0; display: flex;
        flex-direction: column; align-items: center; justify-content: center;
        pointer-events: none; text-align: center; }
    .gm-dona-centro b { font-size: 1.75rem; font-weight: 700; color: #fff;
        letter-spacing: -.02em; font-variant-numeric: tabular-nums; line-height: 1.1; }
    .gm-dona-centro span { font-size: .72rem; color: var(--gm-n-400); margin-top: .15rem;
        max-width: 7.5rem; line-height: 1.3; }
    .gm-leyenda-dona { list-style: none; margin: 0; padding: 0; flex: 1 1 220px;
        display: flex; flex-direction: column; gap: .55rem; min-width: 200px; }
    .gm-leyenda-dona li { display: flex; align-items: center; gap: .6rem;
        font-size: .875rem; }
    .gm-ley-color { width: 10px; height: 10px; border-radius: 3px; flex: 0 0 10px; }
    .gm-ley-et { flex: 1; color: #D3CCD0; }
    .gm-ley-n { font-weight: 600; color: #fff; font-variant-numeric: tabular-nums; }
    .gm-ley-n small { color: var(--gm-n-400); font-weight: 500; }
    .gm-panel-datos { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .75rem 1.25rem; flex: 1 1 260px; padding-left: 1.5rem;
        border-left: 1px solid rgba(255,255,255,.08); }
    .gm-panel-dato span { display: block; font-size: .75rem; color: var(--gm-n-400); }
    .gm-panel-dato b { display: block; font-size: 1.125rem; font-weight: 600;
        color: #fff; font-variant-numeric: tabular-nums; margin-top: .1rem;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .gm-panel-dato small { font-size: .72rem; color: var(--gm-n-400); }

    /* Graficos claros */
    .gm-graf { background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-lg); padding: 1rem 1.125rem;
        box-shadow: var(--gm-sombra-xs); height: 100%; }
    .gm-graf-cab { display: flex; align-items: center; gap: .55rem;
        margin-bottom: .875rem; }
    .gm-graf-cab b { font-size: .9375rem; font-weight: 600; color: var(--gm-n-900); }
    .gm-graf-cab .gm-kpi-ico { width: 1.75rem; height: 1.75rem; flex-basis: 1.75rem; }
    .gm-graf-nota { margin-left: auto; font-size: .75rem; color: var(--gm-n-500); }
    .gm-graf-vacio { font-size: .85rem; color: var(--gm-n-500); padding: 1rem 0; }
    .gm-barras { display: flex; flex-direction: column; gap: .5rem; }
    .gm-barra-fila { display: grid; align-items: center; gap: .6rem;
        grid-template-columns: minmax(7rem, 34%) 1fr auto; }
    .gm-barra-et { font-size: .8125rem; color: var(--gm-n-700); overflow: hidden;
        text-overflow: ellipsis; white-space: nowrap; }
    .gm-barra-pista { height: 10px; background: var(--gm-n-100); border-radius: 999px;
        overflow: hidden; }
    .gm-barra { display: block; height: 100%; border-radius: 999px;
        background: var(--gm-m-500); }
    .gm-barra-fila:hover .gm-barra { background: #FF4FB0; }
    .gm-barra-v { font-size: .8125rem; font-weight: 600; color: var(--gm-n-800);
        font-variant-numeric: tabular-nums; min-width: 2.5rem; text-align: right; }
    .gm-graf-area { width: 100%; height: auto; display: block; overflow: visible; }
    .gm-graf-rej { stroke: var(--gm-n-200); stroke-width: 1; }
    .gm-graf-eje { fill: var(--gm-n-500); font-size: 11px;
        font-family: var(--gm-fuente); font-variant-numeric: tabular-nums; }
    .gm-graf-relleno { fill: rgba(224,17,143,.18); }
    .gm-graf-linea { fill: none; stroke: var(--gm-m-500); stroke-width: 2;
        vector-effect: non-scaling-stroke; stroke-linejoin: round; }
    .gm-graf-hit { fill: transparent; }
    .gm-graf-dot { fill: var(--gm-n-0); stroke: var(--gm-m-500); stroke-width: 2;
        opacity: 0; vector-effect: non-scaling-stroke; }
    .gm-graf-pto:hover .gm-graf-dot { opacity: 1; }

    /* Encabezado de modulo con icono */
    .gm-banner-ico { display: inline-flex; align-items: center; justify-content: center;
        width: 2.75rem; height: 2.75rem; border-radius: var(--gm-r-lg);
        flex: 0 0 2.75rem; }
    .gm-banner-fila2 { display: flex; gap: 1rem; align-items: flex-start; }
    .gm-banner-txt { flex: 1; min-width: 0; }

    /* Cabecera de carga con icono por tipo */
    .gm-carga-ico { display: inline-flex; align-items: center; justify-content: center;
        width: 2rem; height: 2rem; border-radius: var(--gm-r-md); flex: 0 0 2rem; }
    .gm-carga-txt { display: flex; flex-direction: column; min-width: 0; }
    .gm-carga-txt .gm-cod { align-self: flex-start; margin-bottom: .1rem; }

    /* Archivo cargado: marca de "listo" */
    [data-testid="stFileUploaderFile"] { position: relative; }
    [data-testid="stFileUploaderFile"] svg { color: var(--gm-ok); }

    /* Menu lateral: icono sin baldosa (el boton se sombrea completo) */
    section[data-testid="stSidebar"] .stButton > button [data-testid="stIconMaterial"] {
        font-size: 1.15rem;
    }
    /* Tarjeta de la persona (barra lateral) */
    .gm-persona { display: flex; align-items: center; gap: .65rem;
        padding: .7rem .5rem; margin-top: .9rem;
        border-top: 1px solid rgba(255,255,255,.08); }
    .gm-persona * { background: transparent; }
    .gm-avatar { width: 2.125rem; height: 2.125rem; border-radius: 50%;
        flex: 0 0 2.125rem; display: inline-flex; align-items: center;
        justify-content: center; font-size: .78rem; font-weight: 700;
        background: var(--gm-m-600); color: #fff !important; letter-spacing: .02em; }
    .gm-persona-txt { min-width: 0; line-height: 1.3; }
    .gm-persona-txt b { display: block; color: #fff !important; font-weight: 600;
        font-size: .84rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .gm-persona-txt span { font-size: .72rem; color: var(--gm-n-400) !important; }

    /* Inicio: portada oscura */
    .gm-hero { background: linear-gradient(120deg, #1B191A 0%, #2E2A2C 52%, #8E0A5B 100%);
        border: 1px solid rgba(255,255,255,.06); border-radius: 20px;
        padding: 1.5rem 1.75rem; color: #fff; display: flex; gap: 2rem;
        align-items: center; flex-wrap: wrap; margin-bottom: .5rem;
        position: relative; overflow: hidden; }
    .gm-hero::after { content: ""; position: absolute; right: -80px; top: -80px;
        width: 320px; height: 320px; border-radius: 50%; pointer-events: none;
        background: radial-gradient(circle, rgba(255,138,208,.3), transparent 65%); }
    .gm-hero > * { position: relative; z-index: 1; }
    .gm-hero-txt { flex: 1 1 420px; min-width: 0; }
    .gm-hero-txt .gm-eyebrow { color: var(--gm-magenta-claro); }
    .gm-hero-txt h1 { color: #fff !important; font-size: 1.75rem; font-weight: 700;
        letter-spacing: -.02em; margin: 0; padding: 0; line-height: 1.2; }
    .gm-hero-txt p { color: #EDE6EA !important; margin: .45rem 0 0;
        font-size: .9375rem; line-height: 1.55; max-width: 62ch; }
    .gm-hero-datos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1px; background: rgba(255,255,255,.1); border-radius: var(--gm-r-md);
        overflow: hidden; flex: 0 1 420px; }
    .gm-hero-dato { background: rgba(14,12,14,.55); padding: .75rem .9rem; }
    .gm-hero-dato b { display: block; font-size: 1.5rem; font-weight: 700;
        font-variant-numeric: tabular-nums; color: #fff; }
    .gm-hero-dato span { font-size: .75rem; color: #D3CCD0; }
    .gm-tarjeta .gm-tarj-ico { display: inline-flex; align-items: center;
        justify-content: center; width: 2.25rem; height: 2.25rem;
        border-radius: var(--gm-r-md); margin-bottom: .75rem; }


    /* =====================================================================
       v6.14 · Panel de diferencias (reemplaza al visor como vista principal)
       Patrones: CategoryBar (composicion), DeltaBar (partidas), BarList,
       tabla con barra de filtros (busqueda + causas + orden).
       ===================================================================== */
    .gm-comp { background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-lg); padding: 1rem 1.125rem;
        box-shadow: var(--gm-sombra-xs); margin: .25rem 0 .5rem; }
    .gm-comp-cab { display: flex; flex-wrap: wrap; align-items: baseline;
        gap: .25rem 1rem; margin-bottom: .75rem; }
    .gm-comp-cab > b { font-size: .9375rem; font-weight: 600; }
    .gm-comp-cab span { font-size: .8125rem; color: var(--gm-n-500);
        font-variant-numeric: tabular-nums; }
    .gm-comp-cab span b { color: var(--gm-n-900); }
    .gm-comp-barra { display: flex; gap: 2px; height: 1.5rem;
        border-radius: var(--gm-r-md); overflow: hidden; margin-bottom: .5rem; }
    .gm-comp-barra span { display: block; height: 100%; }
    .gm-comp-fila { display: grid; align-items: center; gap: .75rem;
        grid-template-columns: 12px minmax(0, 1fr) auto 4.5rem 9rem;
        padding: .5rem 0; border-top: 1px solid var(--gm-n-100);
        font-size: .8125rem; color: var(--gm-n-700); }
    .gm-comp-fila i { width: 10px; height: 10px; border-radius: 3px; }
    .gm-comp-fila small { color: var(--gm-n-500); }
    .gm-comp-pc { text-align: right; color: var(--gm-n-500);
        font-variant-numeric: tabular-nums; }
    .gm-comp-v { text-align: right; font-weight: 600; color: var(--gm-n-900);
        font-variant-numeric: tabular-nums; }
    .gm-comp-tot { display: flex; justify-content: space-between; gap: 1rem;
        padding-top: .6rem; border-top: 1px solid var(--gm-n-200);
        font-size: .8125rem; color: var(--gm-n-600); }
    .gm-comp-tot b { font-variant-numeric: tabular-nums; color: var(--gm-alerta); }
    .gm-comp-tot b.cero { color: var(--gm-ok); }
    .gm-comp-ok { display: flex; gap: .75rem; align-items: center;
        color: var(--gm-ok); }
    .gm-comp-ok b { display: block; color: var(--gm-n-900); font-size: .9375rem; }
    .gm-comp-ok span { font-size: .8125rem; color: var(--gm-n-500);
        font-variant-numeric: tabular-nums; }

    .gm-pa-lista { background: var(--gm-n-0); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-lg); overflow: hidden;
        box-shadow: var(--gm-sombra-xs); }
    .gm-pa { border-top: 1px solid var(--gm-n-100); }
    .gm-pa:first-child { border-top: 0; }
    .gm-pa > summary { list-style: none; cursor: pointer; display: grid;
        align-items: center; gap: .875rem; padding: .75rem 1rem;
        grid-template-columns: 2rem minmax(0, 1fr) 11.5rem 9rem 8.5rem; }
    .gm-pa > summary::-webkit-details-marker { display: none; }
    .gm-pa > summary:hover { background: var(--gm-n-25); }
    .gm-pa[open] > summary { background: var(--gm-n-25); }
    .gm-pa-txt { min-width: 0; display: flex; flex-wrap: wrap; align-items: baseline;
        gap: .15rem .5rem; }
    .gm-pa-txt > b { font-size: .875rem; font-weight: 600; color: var(--gm-n-900); }
    .gm-pa-tag { font-size: .6875rem; font-weight: 600; padding: .05rem .45rem;
        border-radius: 999px; background: var(--gm-n-100); color: var(--gm-n-600); }
    .gm-pa-tag.valor { background: var(--gm-alerta-bg); color: var(--gm-alerta); }
    .gm-pa-tag.solo_a { background: var(--gm-info-bg); color: var(--gm-info); }
    .gm-pa-tag.solo_b { background: var(--gm-error-bg); color: var(--gm-error); }
    .gm-pa-sub { flex-basis: 100%; font-size: .75rem; color: var(--gm-n-500);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .gm-pa-nota { flex-basis: 100%; font-size: .75rem; color: var(--gm-n-600); }
    .gm-pa-vals { display: flex; flex-direction: column; gap: .1rem;
        font-size: .72rem; color: var(--gm-n-500); text-align: right; }
    .gm-pa-vals b { color: var(--gm-n-800); font-weight: 500;
        font-variant-numeric: tabular-nums; }
    .gm-delta { position: relative; height: .5rem; background: var(--gm-n-100);
        border-radius: 999px; }
    .gm-delta i { position: absolute; left: 50%; top: -3px; bottom: -3px;
        width: 2px; margin-left: -1px; background: var(--gm-n-400);
        border-radius: 2px; }
    .gm-delta-b { position: absolute; top: 0; bottom: 0; border-radius: 999px;
        background: var(--gm-alerta); }
    .gm-delta-b.der { left: 50%; } .gm-delta-b.izq { right: 50%; }
    .gm-delta.vacio { background: transparent; }
    .gm-pa-d { text-align: right; }
    .gm-pa-d b { display: block; font-size: .9375rem; font-weight: 600;
        font-variant-numeric: tabular-nums; color: var(--gm-n-900); }
    .gm-pa-d small { font-size: .6875rem; color: var(--gm-n-500); }
    .gm-pa-det { padding: .25rem 1rem 1rem 3.875rem; }
    .gm-pa-tabla { display: grid; grid-template-columns: 9rem 1fr 1fr;
        gap: .3rem 1rem; font-size: .78rem; background: var(--gm-n-25);
        border: 1px solid var(--gm-n-200); border-radius: var(--gm-r-md);
        padding: .75rem .875rem; font-variant-numeric: tabular-nums; }
    .gm-pa-tabla .h { font-size: .6875rem; text-transform: uppercase;
        letter-spacing: .04em; color: var(--gm-n-500); }
    .gm-pa-tabla span:nth-child(3n+1) { color: var(--gm-n-500); }
    .gm-pa-tabla.r2 { grid-template-columns: 9rem 1fr; }
    .gm-pa-tabla.r2 span { color: inherit; }
    .gm-pa-tabla.r2 span:nth-child(2n+1) { color: var(--gm-n-500); }
    .gm-pa-tabla .dif { color: var(--gm-error); font-weight: 600; }
    .gm-grupo { display: flex; gap: .75rem; align-items: flex-start;
        background: var(--gm-n-25); border: 1px solid var(--gm-n-200);
        border-radius: var(--gm-r-md); padding: .75rem .875rem; margin-top: .5rem; }
    .gm-grupo b { font-size: .8125rem; font-weight: 600; }
    .gm-grupo p { margin: .1rem 0 0; font-size: .75rem; color: var(--gm-n-500); }
    .gm-grupo-v { margin-left: auto; font-weight: 600; font-size: .8125rem;
        font-variant-numeric: tabular-nums; white-space: nowrap; }
    .gm-pa-pie { font-size: .75rem; color: var(--gm-n-500); margin: .5rem .25rem 0; }
    @media (max-width: 900px) {
        .gm-pa > summary { grid-template-columns: 2rem minmax(0, 1fr) 7rem; }
        .gm-pa > summary .gm-delta, .gm-pa > summary .gm-pa-vals { display: none; }
        .gm-comp-fila { grid-template-columns: 12px minmax(0, 1fr) 7rem; }
        .gm-comp-fila .gm-insignia, .gm-comp-fila .gm-comp-pc { display: none; }
    }

    @media (max-width: 900px) {
        .block-container { padding-left: 1rem; padding-right: 1rem; }
        .gm-banner { padding: 1.2rem; }
        .gm-banner img { height: 46px; }
        .gm-banner .gm-sep { display: none; }
        .gm-tarjeta.inicio { min-height: 0; }
        .gm-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .gm-panel-datos { padding-left: 0; border-left: 0; }
        .gm-hero-datos { flex-basis: 100%; }
        div[data-testid="stElementContainer"]:has(.gm-marca-barra)
            + div[data-testid="stElementContainer"],
        div.element-container:has(.gm-marca-barra) + div.element-container
            { right: 3.25rem; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { transition: none !important; }
    }


    /* =====================================================================
       v6.16 · Antiguedad, comparativo y puente (gmya/ui/visual.py)
       ===================================================================== */
    .gm-tramo { display: grid; align-items: center; gap: .75rem;
        grid-template-columns: 12px minmax(0, 1fr) auto 4.5rem minmax(7rem, auto);
        padding: .45rem 0; border-top: 1px solid var(--gm-n-100);
        font-size: .8125rem; color: var(--gm-n-700); }
    .gm-tramo i { width: 10px; height: 10px; border-radius: 3px; }
    .gm-tramo small { color: var(--gm-n-500); white-space: nowrap; font-size: .75rem; }
    .gm-tramo b { text-align: right; font-weight: 600; color: var(--gm-n-900);
        font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
    .gm-tramo.cero { opacity: .55; }
    .gm-barra-v small { display: block; font-size: .6875rem; font-weight: 500;
        color: var(--gm-n-500); }
    .gm-cmp-ley { display: flex; flex-wrap: wrap; gap: .4rem 1rem;
        font-size: .75rem; color: var(--gm-n-500); margin-bottom: .6rem; }
    .gm-cmp-ley span { display: inline-flex; align-items: center; gap: .4rem; }
    .gm-cmp-ley i { width: 10px; height: 10px; border-radius: 3px; }
    .gm-cmp-fila { display: grid; gap: .3rem 1rem; align-items: center;
        grid-template-columns: minmax(8rem, 30%) minmax(0, 1fr);
        padding: .55rem 0; border-top: 1px solid var(--gm-n-100); }
    .gm-cmp-fila:first-of-type { border-top: 0; }
    .gm-cmp-et { display: flex; flex-direction: column; min-width: 0;
        font-size: .8125rem; color: var(--gm-n-800); font-weight: 500; }
    .gm-cmp-et small { font-size: .72rem; color: var(--gm-alerta); font-weight: 500;
        font-variant-numeric: tabular-nums; }
    .gm-cmp-et small.cero { color: var(--gm-ok); }
    .gm-cmp-barras { display: flex; flex-direction: column; gap: .3rem; min-width: 0; }
    .gm-cmp-b { display: grid; grid-template-columns: minmax(0, 1fr) auto;
        align-items: center; gap: .6rem; }
    .gm-cmp-b b { font-size: .78rem; font-weight: 600; color: var(--gm-n-800);
        font-variant-numeric: tabular-nums; text-align: right; min-width: 6.5rem; }
    .gm-cmp .gm-barra-pista { height: 8px; }
    .gm-pte { display: flex; flex-direction: column; }
    .gm-pte-fila { display: grid; align-items: center; gap: .75rem;
        grid-template-columns: minmax(9rem, 32%) minmax(0, 1fr) minmax(7.5rem, auto);
        padding: .4rem 0; border-top: 1px solid var(--gm-n-100);
        font-size: .8125rem; }
    .gm-pte-fila:first-child { border-top: 0; }
    .gm-pte-fila.total .gm-pte-et, .gm-pte-fila.total .gm-pte-v { font-weight: 600;
        color: var(--gm-n-900); }
    .gm-pte-et { color: var(--gm-n-700); min-width: 0; }
    .gm-pte-pista { position: relative; height: 14px; background: var(--gm-n-100);
        border-radius: 4px; }
    .gm-pte-b { position: absolute; top: 2px; bottom: 2px; border-radius: 3px; }
    .gm-pte-b.mas { background: #5FD3CB; }
    .gm-pte-b.menos { background: var(--gm-m-500); }
    .gm-pte-total { position: absolute; top: -3px; bottom: -3px; width: 3px;
        margin-left: -1.5px; border-radius: 2px; background: var(--gm-n-900); }
    .gm-pte-v { text-align: right; font-variant-numeric: tabular-nums;
        color: var(--gm-n-800); font-weight: 500; overflow-wrap: anywhere; }
    @media (max-width: 900px) {
        .gm-tramo { grid-template-columns: 12px minmax(0, 1fr) auto minmax(6rem, auto); }
        .gm-tramo .gm-comp-pc { display: none; }
        .gm-cmp-fila, .gm-pte-fila { grid-template-columns: minmax(0, 1fr); }
    }

    /* v6.17 · columnas por hora, mapa de calor y linea de tiempo */
    .gm-cols { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr;
        gap: 3px; height: 190px; align-items: end; padding-top: 1.1rem; }
    .gm-col { position: relative; height: 100%; display: flex;
        flex-direction: column; justify-content: flex-end; align-items: center;
        min-width: 0; }
    .gm-col span { width: 100%; background: rgba(224,17,143,.55);
        border-radius: 3px 3px 0 0; }
    .gm-col:hover span { background: #FF4FB0; }
    .gm-col.max span { background: var(--gm-m-500); }
    .gm-col em { position: absolute; top: -1.1rem; font-style: normal;
        font-size: .6875rem; font-weight: 600; color: var(--gm-n-900);
        white-space: nowrap; }
    .gm-col small { height: 1rem; margin-top: .3rem; font-size: .6875rem;
        color: var(--gm-n-500); white-space: nowrap; }
    .gm-calor { display: grid; gap: 2px; align-items: center;
        grid-template-columns: 2.4rem repeat(var(--gm-ncols), minmax(0, 1fr)); }
    .gm-calor b { font-size: .72rem; font-weight: 500; color: var(--gm-n-600); }
    .gm-calor small { font-size: .6875rem; color: var(--gm-n-500);
        white-space: nowrap; overflow: visible; }
    .gm-calor i { display: block; aspect-ratio: 1.6 / 1; border-radius: 3px;
        background: var(--gm-n-100); min-height: 10px; }
    .gm-calor i:hover { outline: 2px solid var(--gm-n-900); }
    .gm-calor-ley { display: flex; align-items: center; gap: .5rem;
        margin-top: .75rem; font-size: .72rem; color: var(--gm-n-500); }
    .gm-calor-esc { display: inline-flex; gap: 2px; }
    .gm-calor-esc i { width: 18px; height: 10px; border-radius: 2px; }
    .gm-lt { display: flex; flex-direction: column; gap: .35rem; }
    .gm-lt + .gm-cmp-ley { margin: .85rem 0 0; }
    .gm-lt-fila { display: grid; align-items: center; gap: .75rem;
        grid-template-columns: minmax(7rem, 22%) minmax(0, 1fr); }
    .gm-lt-et { font-size: .8125rem; color: var(--gm-n-800); min-width: 0;
        overflow-wrap: anywhere; }
    .gm-lt-eje { position: relative; height: 1rem; }
    .gm-lt-eje small { position: absolute; transform: translateX(-50%);
        font-size: .6875rem; color: var(--gm-n-500); white-space: nowrap; }
    .gm-lt-eje small:first-child { transform: none; }
    .gm-lt-eje small:last-child { transform: translateX(-100%); }
    .gm-lt-pista { position: relative; height: 18px; border-radius: 4px;
        background: var(--gm-n-100); overflow: hidden; }
    .gm-lt-pista u { position: absolute; top: 0; bottom: 0; width: 1px;
        background: rgba(255,255,255,.06); }
    .gm-lt-t { position: absolute; top: 3px; bottom: 3px; border-radius: 3px; }
    .gm-lt-t.uso { background: var(--gm-m-500); }
    .gm-lt-t.abierta { background: #5E585B; }
    @media (max-width: 900px) {
        .gm-lt-fila { grid-template-columns: minmax(0, 1fr); }
        .gm-lt-cab > span:first-child { display: none; }
    }
    /* =====================================================================
       v6.15 · Nada queda oculto: los textos y cifras se ajustan al ancho del
       contenedor (letra que se reduce hasta un minimo legible y, si aun no
       cabe, pasa a la siguiente linea) en vez de cortarse con "...".
       Letra minima 11px.
       ===================================================================== */
    div[data-testid="stMetric"], .gm-kpi, .gm-panel-dato { container-type: inline-size; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div {
        font-size: clamp(1.05rem, 9cqi, 1.5rem) !important;
        white-space: normal !important; overflow: visible !important;
        text-overflow: clip !important; overflow-wrap: anywhere;
    }
    div[data-testid="stMetricLabel"] p, div[data-testid="stMetric"] label {
        white-space: normal !important; overflow: visible !important;
    }
    .gm-kpi-val { font-size: clamp(1.05rem, 10cqi, 1.5rem); white-space: normal;
        overflow: visible; text-overflow: clip; overflow-wrap: anywhere; }
    .gm-kpi-et { white-space: normal; overflow: visible; line-height: 1.3;
        flex: 1 1 auto; min-width: auto; }
    .gm-emp-off { flex-wrap: wrap; }
    .gm-kpi-cab { flex-wrap: wrap; }
    .gm-panel-dato b { font-size: clamp(.95rem, 11cqi, 1.125rem); white-space: normal;
        overflow: visible; text-overflow: clip; overflow-wrap: anywhere; }
    .gm-barra-fila { grid-template-columns: minmax(7rem, 40%) 1fr auto; }
    .gm-barra-et { white-space: normal; overflow: visible; line-height: 1.3; }
    .gm-emp-off .gm-emp-nombre { white-space: normal; overflow: visible; line-height: 1.3; }
    .gm-pa-sub { white-space: normal; overflow: visible; }
    .gm-persona-txt b { white-space: normal; overflow: visible; }
    .gm-tarjeta h3 { flex-wrap: wrap; }
    .gm-glo-chip .gm-ayuda { font-size: .6875rem; }
    [data-testid="stFileUploaderDropzone"] { flex-wrap: wrap; row-gap: .5rem; }
    .gm-comp-fila > span:first-of-type { overflow-wrap: anywhere; }
    .gm-pa-vals b, .gm-pa-d b { overflow-wrap: anywhere; }
    /* v6.18 · avisos agrupados (EMPRESA B) */
.gm-avisos{margin:.2rem 0 .4rem;padding-left:1.1rem;font-size:.86rem;line-height:1.5;color:var(--gm-txt-2,#D9D2D6)}
.gm-avisos li{margin:.2rem 0;overflow-wrap:anywhere}
</style>
    """


def aplicar_estilos():
    """Inyecta la hoja de estilos de la marca GMYA. Se llama en cada
    ejecucion desde app.py."""
    st.markdown(CSS_GMYA, unsafe_allow_html=True)
