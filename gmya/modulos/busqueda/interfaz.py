"""Pantalla "Busqueda de archivos" (Streamlit).

Contrato:
  modulo_busqueda() -> pinta la pantalla.
  precalentar_indice_drive() -> arranca el indice en segundo plano; app.py
      lo llama en cada ejecucion (es barato si ya esta construido).

Depende de: gmya.comun.texto, gmya.comun.cache, gmya.comun.config_equipo, gmya.ui.componentes, gmya.modulos.busqueda.logica, gmya.registro.interfaz
"""

from pathlib import Path

import streamlit as st

from gmya.comun.texto import comparable
from gmya.comun.cache import _cache_datos, _cache_recurso
from gmya.comun.config_equipo import guardar_config, leer_config
from gmya.ui.componentes import banner_modulo, titulo_seccion
from gmya.modulos.busqueda.logica import (
    abrir_en_sistema, carpeta_componente_explorador, datos_carpeta_visor,
    datos_resultados_visor, detectar_carpeta_empresas, detectar_rutas_drive,
    extension, FECHAS_FILTRO, IndiceDrive, listar_empresas, ORDEN_RESULTADOS,
    ruta_dentro_de, TIPOS_ARCHIVO, validar_ruta_drive,
)
from gmya.registro.interfaz import registrar_uso, reportar_error


# ============================================================
# INTERFAZ: BUSQUEDA DE ARCHIVOS (GOOGLE DRIVE - MI UNIDAD)
# ============================================================
TODAS_EMPRESAS = "Todas las empresas"
AMBITO_EMPRESAS = "Empresas activas (uso diario)"
AMBITO_TODO = "Todo Mi unidad"


def _componente_explorador():
    import streamlit.components.v1 as componentes
    return componentes.declare_component(
        "gmya_explorador_drive", path=str(carpeta_componente_explorador()))


@_cache_recurso
def _registro_indices():
    """Indices en memoria del proceso (no se copian en cada recarga)."""
    return {}


def _indice(raiz):
    registro = _registro_indices()
    clave = str(raiz)
    if clave not in registro:
        registro[clave] = IndiceDrive(clave)
    return registro[clave]


def precalentar_indice_drive():
    """
    Al abrir la plataforma se empieza a leer (en segundo plano) la carpeta
    de empresas guardada, para que la primera busqueda sea inmediata.
    """
    # Una sola vez por sesion: antes se revisaba en cada clic de cualquier
    # modulo (leer la configuracion y tocar la unidad G: cada vez).
    if st.session_state.get("busq_precalentado"):
        return
    st.session_state["busq_precalentado"] = True
    try:
        config = leer_config()
        ruta = config.get("ruta_empresas") or config.get("ruta_drive")
        if ruta and Path(ruta).is_dir():
            _indice(ruta).actualizar()       # proceso aparte, prioridad baja
    except Exception:
        pass


@_cache_datos
def _rutas_drive_detectadas():
    # Revisar las unidades C: a Z: puede tardar (unidades de red): una vez
    # por hora basta.
    return detectar_rutas_drive()


def _cache_corto(funcion):
    decorador = getattr(st, "cache_data", None)
    return decorador(show_spinner=False, ttl=300, max_entries=8)(funcion) \
        if decorador else funcion


@_cache_corto
def _empresas_de(carpeta_empresas):
    return listar_empresas(carpeta_empresas)


@_cache_datos
def _carpeta_empresas_detectada(mi_unidad):
    encontradas = detectar_carpeta_empresas(mi_unidad)
    return encontradas[0] if encontradas else ""


def _actualizar_indice():
    base = st.session_state.get("busq_base")
    if base:
        _indice(base).actualizar(forzar=True)


def _estado_indice(indice):
    """Linea de estado del indice; se refresca sola mientras se construye."""
    def linea():
        if indice.construyendo:
            texto = (f"⏳ Leyendo las carpetas en segundo plano… "
                     f"{indice.leidos:,} elementos")
            if indice.entradas:
                texto += (" · mientras tanto se busca con el índice "
                          f"anterior ({indice.edad_texto()})")
            else:
                texto += " · los resultados se completan solos al terminar"
            st.caption(texto)
        else:
            st.caption(f"Índice: {len(indice.entradas):,} elementos · "
                       f"{indice.edad_texto()}"
                       + (" · algunas carpetas no se pudieron leer"
                          if not indice.completo else "")
                       + (f" · error: {indice.error}" if indice.error
                          else ""))

    fragmento = getattr(st, "fragment", None)
    if indice.construyendo and fragmento:
        estado = {"seguia": True, "primera": not indice.entradas}

        @fragmento(run_every=3)
        def vigilar():
            linea()
            if estado["seguia"] and not indice.construyendo:
                estado["seguia"] = False
                if estado["primera"]:
                    st.rerun()               # primera lectura: mostrar todo
                else:
                    st.toast("Índice de archivos actualizado.")
        try:
            vigilar()
            return
        except TypeError:                    # Streamlit sin run_every
            pass
    linea()


def _empresa_de(ruta, carpeta_empresas):
    """Nombre de la empresa (carpeta de primer nivel) que contiene la ruta."""
    if not carpeta_empresas or not ruta_dentro_de(ruta, carpeta_empresas):
        return None
    partes = Path(ruta).resolve().relative_to(
        Path(carpeta_empresas).resolve()).parts
    return partes[0] if partes else None


def _al_cambiar_empresa():
    empresa = st.session_state.get("busq_empresa")
    base = st.session_state.get("busq_base") or ""
    st.session_state["busq_actual"] = str(Path(base) / empresa) \
        if empresa and empresa != TODAS_EMPRESAS and base else base


def _al_cambiar_ambito():
    st.session_state["busq_actual"] = ""
    st.session_state["busq_empresa"] = TODAS_EMPRESAS


def _limpiar_filtros():
    st.session_state["busq_texto"] = ""
    st.session_state["busq_tipos"] = []
    st.session_state["busq_fecha"] = "Cualquier fecha"


def _procesar_clic_explorador(valor, raices, carpeta_empresas, buscando):
    if not isinstance(valor, dict) or not valor.get("t"):
        return
    if valor["t"] == st.session_state.get("busq_ultimo_t"):
        return                                  # clic ya atendido
    st.session_state["busq_ultimo_t"] = valor["t"]
    ruta = str(valor.get("ruta") or "")
    accion = valor.get("accion")
    if accion in ("abrir", "ubicar"):
        try:
            abrir_en_sistema(ruta, raices, ubicar=accion == "ubicar")
            registrar_uso("abrir", "ubicar en el Explorador"
                          if accion == "ubicar" else
                          ("carpeta" if Path(ruta).is_dir() else
                           f"archivo .{extension(Path(ruta).name)}"))
            st.toast(("Mostrando en el Explorador: " if accion == "ubicar"
                      else "Abriendo ") + f"«{Path(ruta).name or ruta}»")
        except Exception as error:
            reportar_error("No se pudo abrir", error)
    elif accion == "navegar":
        if not ruta or not any(ruta_dentro_de(ruta, r) for r in raices):
            return
        pendiente = {}
        st.session_state["busq_actual"] = ruta
        if carpeta_empresas and ruta_dentro_de(ruta, carpeta_empresas) and \
                st.session_state.get("busq_ambito") == AMBITO_EMPRESAS:
            pendiente["busq_empresa"] = _empresa_de(ruta, carpeta_empresas) \
                or TODAS_EMPRESAS
        if buscando:                            # ver la carpeta: sin filtros
            pendiente.update({"busq_texto": "", "busq_tipos": [],
                              "busq_fecha": "Cualquier fecha"})
        st.session_state["busq_pendiente"] = pendiente
        st.rerun()


def _configuracion_rutas():
    """Ruta de Mi unidad y de la carpeta de empresas (se recuerdan)."""
    config = leer_config()
    if "busq_ruta_txt" not in st.session_state:
        detectadas = _rutas_drive_detectadas()
        st.session_state["busq_ruta_txt"] = config.get("ruta_drive") or (
            detectadas[0] if detectadas else "")
    raiz, mensaje, nivel = validar_ruta_drive(
        st.session_state["busq_ruta_txt"])
    with st.expander("Rutas de Google Drive" + (
            f" · {raiz}" if raiz else " · falta configurar"),
            expanded=raiz is None):
        st.text_input(
            "Ruta de la carpeta «Mi unidad»", key="busq_ruta_txt",
            placeholder="G:\\Mi unidad",
            help="Abre Mi unidad en el Explorador de Windows, haz clic en la "
                 "barra de direcciones y copia la ruta.")
        detectadas = _rutas_drive_detectadas()
        if detectadas:
            st.caption("Encontradas en este equipo: " + " · ".join(
                f"`{d}`" for d in detectadas))
        if raiz is None:
            (st.info if not st.session_state["busq_ruta_txt"]
             else st.error)(mensaje)
            return None, None
        if nivel == "aviso":
            st.warning(mensaje)
        if config.get("ruta_drive") != str(raiz):
            guardar_config(ruta_drive=str(raiz))

        if "busq_empresas_txt" not in st.session_state:
            guardada = config.get("ruta_empresas") or ""
            st.session_state["busq_empresas_txt"] = guardada if guardada \
                and Path(guardada).is_dir() else \
                _carpeta_empresas_detectada(str(raiz))
        st.text_input(
            "Carpeta de empresas (001. EMPRESAS ACTIVAS USO DIARIO)",
            key="busq_empresas_txt",
            help="Se detecta sola dentro de Mi unidad o de Unidades "
                 "compartidas. Tiene una subcarpeta por empresa. Solo se "
                 "lee: la plataforma nunca escribe en ella.")
        empresas_txt = str(st.session_state["busq_empresas_txt"]).strip() \
            .strip('"')
        carpeta_empresas = empresas_txt if empresas_txt and \
            Path(empresas_txt).is_dir() else ""
        if empresas_txt and not carpeta_empresas:
            st.error("No existe esa carpeta de empresas en este equipo.")
        elif not carpeta_empresas:
            st.caption("No se encontró la carpeta «001. EMPRESAS ACTIVAS USO "
                       "DIARIO»; se buscará en todo Mi unidad.")
        elif config.get("ruta_empresas") != carpeta_empresas:
            guardar_config(ruta_empresas=carpeta_empresas)
    return raiz, carpeta_empresas


def modulo_busqueda():
    banner_modulo(
        "Módulo · Archivos",
        "Búsqueda de archivos",
        "Encuentra en segundos los documentos de cada empresa en Google "
        "Drive: busca por nombre, filtra por empresa, tipo y fecha, y abre "
        "el archivo o su carpeta con un clic. Solo lectura: no se mueve ni "
        "se borra nada.",
        ("001. Empresas activas", "Filtros por empresa, tipo y fecha",
         "Abre en el Explorador"),
    )

    # Cambios pedidos desde el explorador (antes de dibujar los controles).
    for clave, valor in (st.session_state.pop("busq_pendiente", None)
                         or {}).items():
        st.session_state[clave] = valor

    raiz, carpeta_empresas = _configuracion_rutas()
    if raiz is None:
        return
    raices = [str(raiz)] + ([carpeta_empresas] if carpeta_empresas else [])

    # ---- Barra de busqueda y filtros ----
    titulo_seccion(
        "Buscar", 1,
        "Escribe parte del nombre (sin importar tildes ni mayúsculas; si "
        "escribes varias palabras deben estar todas). Los filtros funcionan "
        "también sin texto: por ejemplo, empresa + Excel + últimos 30 días "
        "lista los Excel recientes de esa empresa. La primera búsqueda lee "
        "todas las carpetas; después es inmediata.")
    ambitos = [AMBITO_EMPRESAS, AMBITO_TODO] if carpeta_empresas \
        else [AMBITO_TODO]
    if st.session_state.get("busq_ambito") not in ambitos:
        st.session_state["busq_ambito"] = ambitos[0]
    c1, c2 = st.columns([3.2, 1.4])
    consulta = c1.text_input(
        "Buscar archivo o carpeta", key="busq_texto",
        placeholder="Ej.: extracto bancolombia septiembre",
        label_visibility="collapsed")
    ambito = c2.selectbox("Dónde buscar", ambitos, key="busq_ambito",
                          label_visibility="collapsed",
                          on_change=_al_cambiar_ambito)
    base = carpeta_empresas if ambito == AMBITO_EMPRESAS else str(raiz)
    if st.session_state.get("busq_base") != base:
        st.session_state["busq_base"] = base
        st.session_state["busq_actual"] = ""

    f1, f2, f3, f4, f5 = st.columns([1.6, 1.8, 1.1, 1.1, 0.9])
    empresa = None
    if ambito == AMBITO_EMPRESAS:
        nombres = [TODAS_EMPRESAS] + [n for n, _ in
                                      _empresas_de(carpeta_empresas)]
        if st.session_state.get("busq_empresa") not in nombres:
            st.session_state["busq_empresa"] = TODAS_EMPRESAS
        elegida = f1.selectbox("Empresa", nombres, key="busq_empresa",
                               on_change=_al_cambiar_empresa,
                               help="Escribe para filtrar la lista.")
        empresa = None if elegida == TODAS_EMPRESAS else elegida
    else:
        f1.selectbox("Empresa", ["(solo en Empresas activas)"],
                     disabled=True)
    tipos = f2.multiselect("Tipo", list(TIPOS_ARCHIVO) + ["Otros"],
                           key="busq_tipos", placeholder="Todos los tipos")
    fecha = f3.selectbox("Modificado", list(FECHAS_FILTRO), key="busq_fecha")
    orden = f4.selectbox("Ordenar", ORDEN_RESULTADOS, key="busq_orden")
    f5.write("")
    f5.button("↻ Índice", key="busq_refrescar", on_click=_actualizar_indice,
              use_container_width=True,
              help="Vuelve a leer las carpetas (si agregaste archivos).")

    buscando = bool(comparable(consulta).replace(" ", "")) or bool(tipos) \
        or fecha != "Cualquier fecha"

    # ---- Explorador ----
    indice = _indice(base)
    indice.actualizar(interactivo=True)  # refresca en segundo plano si vencio
    if buscando:
        resultados, parcial = indice.buscar(consulta, empresa, tipos, fecha,
                                            orden)
        firma_busq = (comparable(consulta), empresa or "",
                      tuple(tipos or []), fecha)
        if st.session_state.get("reg_busqueda") != firma_busq:
            st.session_state["reg_busqueda"] = firma_busq
            registrar_uso("búsqueda", f"{len(resultados)} resultados"
                          + (" · filtro por empresa" if empresa else "")
                          + (f" · tipos: {', '.join(tipos)}" if tipos else "")
                          + (f" · {fecha}" if fecha != "Cualquier fecha"
                             else ""))
        datos = datos_resultados_visor(resultados, base, consulta)
        c1, c2 = st.columns([5, 1.2])
        with c1:
            _estado_indice(indice)
        c2.button("Limpiar filtros", key="busq_limpiar",
                  on_click=_limpiar_filtros, use_container_width=True)
    else:
        actual = st.session_state.get("busq_actual") or ""
        if not actual or not Path(actual).is_dir() or \
                not any(ruta_dentro_de(actual, r) for r in raices):
            actual = str(Path(base) / empresa) if empresa else base
            st.session_state["busq_actual"] = actual
        datos = datos_carpeta_visor(
            actual, [base] + [r for r in raices if r != base])

    titulo_seccion(
        "Resultados" if buscando else "Explorador", 2,
        "<b>Carpeta</b>: clic para entrar; ↗ la abre en el Explorador de "
        "Windows. <b>Archivo</b>: clic para abrirlo con su programa. En los "
        "resultados, <b>Ubicar</b> abre la carpeta con el archivo "
        "seleccionado y <b>Ver carpeta</b> la muestra aquí. La barra de "
        "arriba permite volver a cualquier nivel.")
    try:
        valor = _componente_explorador()(datos=datos, alto=620,
                                          key="busq_explorador",
                                          default=None)
    except Exception as error:
        reportar_error("No se pudo mostrar el explorador", error)
        return
    _procesar_clic_explorador(valor, raices, carpeta_empresas, buscando)
