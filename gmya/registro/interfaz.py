"""Pantallas y envoltorios del registro de uso (Streamlit).

Contrato:
  pantalla_quien_usa(carpeta, modo_admin=False) -> pantalla de entrada.
  _instalar_registro_en_streamlit() -> envuelve st.button, download_button,
      file_uploader y error para registrar acciones (idempotente).
  registrar_uso(evento, detalle) -> escribe en segundo plano.
  reportar_error(mensaje, error) -> muestra el error en lenguaje sencillo
      (que paso, que significa, que hacer) con el detalle tecnico plegado,
      y lo registra con el tipo de error y el archivo/linea del codigo
      (sin nombres de archivos ni datos de clientes).
  modulo_uso() -> pantalla "Uso de la plataforma" (solo administradores).
REGLA DE SEGURIDAD: solo un administrador puede cambiarse de usuario; una
sesion de un usuario no administrador nunca puede cambiar de persona ni
elegir un administrador.

Depende de: gmya.comun.texto, gmya.comun.cache, gmya.comun.config_equipo, gmya.ui.componentes, gmya.modulos.busqueda.logica, gmya.registro.logica
"""

import datetime
import html
import io
from collections import Counter
from pathlib import Path

import streamlit as st

from gmya.comun.texto import comparable
from gmya.comun.cache import _cache_recurso
from gmya.comun.config_equipo import guardar_config
from gmya.ui.componentes import banner_modulo, titulo_seccion
from gmya.modulos.busqueda.logica import extension
from gmya.registro.logica import (
    asignar_persona, carpeta_gmya, codigo_equipo, COLUMNAS_REGISTRO,
    equipo_de_admin, _es_carpeta_de_empresas, escribir_registro,
    explicar_error, leer_registros, leer_usuarios, MINUTOS_LATIDO, MODULOS_NOMBRE,
    nombre_equipo, nombres_admin, persona_del_equipo, resumen_uso,
    texto_seguro_registro,
)


# ============================================================
# INTERFAZ: USUARIO DEL EQUIPO Y REGISTRO DE USO
# ============================================================
AVISO_REGISTRO = (
    "La plataforma registra qué módulos y acciones se usan en este equipo "
    "(sin datos de clientes ni contenido de archivos) para saber si la "
    "herramienta les es útil y cómo mejorarla.")


def _estado_registro():
    """Carpeta GMYA Tools y persona de este equipo (una vez por sesion)."""
    if "reg_carpeta" not in st.session_state:
        st.session_state["reg_carpeta"] = carpeta_gmya()
    if "reg_sesion" not in st.session_state:
        import uuid
        st.session_state["reg_sesion"] = uuid.uuid4().hex[:8]
    carpeta = st.session_state["reg_carpeta"]
    if "reg_persona" not in st.session_state:
        st.session_state["reg_persona"] = persona_del_equipo(carpeta)
        st.session_state["reg_equipo_admin"] = equipo_de_admin(carpeta)
    return carpeta, st.session_state["reg_persona"]


@_cache_recurso
def _escritor_registro():
    """Un solo hilo que escribe los registros en el Drive, para que la
    pagina nunca espere a la unidad G: (Drive puede tardar al sincronizar)."""
    from concurrent.futures import ThreadPoolExecutor
    return ThreadPoolExecutor(max_workers=1,
                              thread_name_prefix="gmya-registro")


def _escribir_sin_error(*args, **kwargs):
    try:
        escribir_registro(*args, **kwargs)
    except Exception:
        pass


def registrar_uso(evento, detalle="", interacciones=""):
    """Registra un evento de la sesion actual (nunca interrumpe ni hace
    esperar: se escribe en segundo plano)."""
    try:
        argumentos = dict(
            modulo=st.session_state.get("modulo_gmya", ""),
            persona=st.session_state.get("reg_persona", ""),
            sesion=st.session_state.get("reg_sesion", ""),
            interacciones=interacciones,
            carpeta=st.session_state.get("reg_carpeta"),
            momento=datetime.datetime.now())
        try:
            _escritor_registro().submit(_escribir_sin_error, evento, detalle,
                                        **argumentos)
        except Exception:
            _escribir_sin_error(evento, detalle, **argumentos)
    except Exception:
        pass


def _ubicacion_error(error):
    """'modulo.py:linea funcion' de los puntos del codigo de GMYA por donde
    paso el error (del mas externo al mas interno). Sin datos de clientes."""
    import traceback
    pasos = []
    for marco in traceback.extract_tb(getattr(error, "__traceback__", None)):
        ruta = str(marco.filename).replace("\\", "/")
        if "/gmya/" in ruta:
            corto = ruta.split("/gmya/", 1)[1]
            pasos.append(f"{corto}:{marco.lineno} {marco.name}")
    return pasos


def _lanzado_por_gmya(error):
    """True si el error lo lanzo el codigo de GMYA (raise ValueError con un
    mensaje en espanol) y no una libreria."""
    import traceback
    marcos = traceback.extract_tb(getattr(error, "__traceback__", None))
    return bool(marcos) and "/gmya/" in str(
        marcos[-1].filename).replace("\\", "/")


def reportar_error(mensaje, error):
    """
    Muestra un error comprensible y lo deja en el registro de uso.
      mensaje: que se estaba haciendo ("No se pudo generar la conciliacion").
      error:   la excepcion capturada.
    En pantalla: mensaje + que significa + que hacer, y un desplegable con
    el detalle tecnico. En el registro: mensaje, tipo de error y ubicacion
    en el codigo (texto_seguro_registro quita nombres de archivo y rutas).
    """
    tipo = type(error).__name__
    texto_error = str(error)
    _, significado, hacer = explicar_error(f"{mensaje} {tipo} {texto_error}")
    pasos = _ubicacion_error(error)
    propio = tipo == "ValueError" and " " in texto_error and \
        _lanzado_por_gmya(error)
    try:
        detalle = texto_seguro_registro(
            f"{mensaje} · {tipo}: {texto_error}", 160)
        donde = pasos[-1] if pasos else ""
        registrar_uso("error", f"{detalle} · en {donde}" if donde
                      else detalle)
        # v6.7: para adjuntarlos al "Reportar un error" de esta sesion.
        recientes = st.session_state.setdefault("reg_errores_sesion", [])
        recientes.append(f"{datetime.datetime.now():%H:%M:%S} · "
                         f"{mensaje} · {tipo}: {texto_error[:200]}"
                         + (f" · en {donde}" if donde else ""))
        del recientes[:-10]
    except Exception:
        pass
    mostrar = getattr(st, "_gmya_error_original", st.error)
    if propio:
        # Mensaje escrito por la plataforma (ya explica el problema).
        mostrar(f"**{mensaje}.** {texto_error}")
    else:
        mostrar(f"**{mensaje}.** {significado}\n\n**Qué hacer:** {hacer}")
    with st.expander("Detalle técnico (para el administrador)"):
        st.code(f"{tipo}: {texto_error}\n"
                + ("\n".join("  en " + p for p in pasos) or ""),
                language=None)


def _instalar_registro_en_streamlit():
    """
    Envuelve botones, descargas, cargas de archivos y mensajes de error de
    Streamlit para registrar la actividad sin tocar cada modulo. Los
    envoltorios llaman a st._gmya_registrar, que se actualiza en cada
    ejecucion.
    """
    st._gmya_registrar = registrar_uso
    if getattr(st, "_gmya_envuelto", False) is True:
        return
    st._gmya_envuelto = True
    st._gmya_error_original = st.error
    original_boton = st.button
    original_descarga = st.download_button
    original_carga = st.file_uploader
    original_error = st.error

    def registrar(*args, **kwargs):
        funcion = getattr(st, "_gmya_registrar", None)
        if funcion:
            funcion(*args, **kwargs)

    def omitir(kwargs):
        clave = str(kwargs.get("key") or "")
        return clave.startswith(("menu_", "ir_", "pp_emp", "reg_",
                                 "uso_"))

    def boton(label, *args, **kwargs):
        retorno = kwargs.get("on_click")
        if retorno and not omitir(kwargs):
            def con_registro(*a, **k):
                registrar("clic", texto_seguro_registro(label))
                return retorno(*a, **k)
            kwargs["on_click"] = con_registro
        pulsado = original_boton(label, *args, **kwargs)
        if pulsado and not retorno and not omitir(kwargs):
            registrar("clic", texto_seguro_registro(label))
        return pulsado

    def descarga(label, *args, **kwargs):
        retorno = kwargs.get("on_click")
        if not omitir(kwargs) and (retorno is None or callable(retorno)):
            def con_registro(*a, **k):
                registrar("descarga", texto_seguro_registro(label))
                if callable(retorno):
                    return retorno(*a, **k)
            kwargs["on_click"] = con_registro
        return original_descarga(label, *args, **kwargs)

    def carga(label, *args, **kwargs):
        valor = original_carga(label, *args, **kwargs)
        try:
            archivos = valor if isinstance(valor, (list, tuple)) else (
                [valor] if valor else [])
            firma = tuple(sorted((a.name, a.size) for a in archivos))
            llave = f"reg_carga_{kwargs.get('key') or label}"
            if archivos and st.session_state.get(llave) != firma:
                st.session_state[llave] = firma
                tipos = Counter(extension(a.name) or "?" for a in archivos)
                registrar("carga", f"{len(archivos)} archivo(s): " +
                          ", ".join(f"{n} .{t}" for t, n in tipos.items()))
            elif not archivos:
                st.session_state.pop(llave, None)
        except Exception:
            pass
        return valor

    def error(body, *args, **kwargs):
        registrar("error", texto_seguro_registro(body, 140))
        return original_error(body, *args, **kwargs)

    st.button = boton
    st.download_button = descarga
    st.file_uploader = carga
    st.error = error


def _latido_registro():
    """Cada 10 minutos, mientras la pestana este abierta, deja una linea
    'abierta' con las interacciones de ese lapso (0 = abierta sin uso)."""
    fragmento = getattr(st, "fragment", None)
    if not fragmento:
        return

    @fragmento(run_every=60)
    def latido():
        ahora = datetime.datetime.now()
        ultimo = st.session_state.get("reg_ultimo_latido")
        if ultimo is None:
            st.session_state["reg_ultimo_latido"] = ahora
            return
        if (ahora - ultimo).total_seconds() < MINUTOS_LATIDO * 60 - 5:
            return
        st.session_state["reg_ultimo_latido"] = ahora
        n = st.session_state.get("reg_interacciones", 0)
        st.session_state["reg_interacciones"] = 0
        registrar_uso("abierta", f"{MINUTOS_LATIDO} min", interacciones=n)
    try:
        latido()
    except TypeError:
        pass


OTRA_PERSONA = "Otra persona (escribir)"
VOLVER_ADMIN = "↩ Volver a mi usuario (según equipos.txt)"


def _guardar_persona(carpeta, modo_admin):
    eleccion = st.session_state.get("reg_eleccion") or ""
    if eleccion == OTRA_PERSONA:
        eleccion = st.session_state.get("reg_otro") or ""
    eleccion = eleccion.strip()
    if modo_admin and eleccion == VOLVER_ADMIN:
        guardar_config(persona="", persona_por_admin=False)
    else:
        if not eleccion:
            st.session_state["reg_falta"] = "Escoge o escribe un nombre."
            return
        # Un administrador nunca se puede escoger desde un equipo que no es
        # de administrador (se valida aqui, no solo en la lista).
        if not modo_admin and comparable(eleccion) in nombres_admin(carpeta):
            st.session_state["reg_falta"] = (
                "Ese nombre corresponde a un administrador y no se puede "
                "escoger aquí. Escoge tu nombre.")
            return
        asignar_persona(eleccion, por_admin=modo_admin)
    anterior = st.session_state.get("reg_persona", "")
    for llave in ("reg_persona", "reg_eleccion", "reg_otro", "reg_cambiando",
                  "reg_admin_de"):
        st.session_state.pop(llave, None)
    st.session_state["reg_persona"] = persona_del_equipo(carpeta)
    registrar_uso("cambio de usuario" if modo_admin else "equipo asignado",
                  (f"antes: {anterior}" if modo_admin and anterior else
                   f"equipo {codigo_equipo()} · "
                   f"{texto_seguro_registro(nombre_equipo())}"))


def pantalla_quien_usa(carpeta, modo_admin=False):
    """
    Primera vez en el equipo (modo normal): solo se puede escoger una
    persona que NO sea administrador. En un equipo de administrador
    (modo_admin) se puede escoger cualquiera o volver al propio usuario.
    """
    if modo_admin:
        banner_modulo(
            "Equipo de administrador", "Cambiar de usuario",
            "Escoge con qué persona se registrará la actividad en este "
            "equipo. Solo los equipos asignados a un administrador en "
            "equipos.txt pueden hacer este cambio.",
            ("Solo administradores", f"Equipo {codigo_equipo()}"))
    else:
        banner_modulo(
            "Primera vez en este equipo",
            "¿Quién usa este computador?",
            "Escoge tu nombre una sola vez. No hay contraseña: la plataforma "
            "recordará que este equipo es tuyo y no se podrá cambiar desde "
            "aquí. " + AVISO_REGISTRO,
            ("Una sola vez", "Sin contraseña", f"Equipo {codigo_equipo()}"))
    usuarios = leer_usuarios(carpeta)
    if modo_admin:
        opciones = [VOLVER_ADMIN] + [n for n, _ in usuarios] + [OTRA_PERSONA]
    else:
        opciones = [n for n, admin in usuarios if not admin]
        if not opciones:
            opciones = [OTRA_PERSONA]
    c1, _ = st.columns([1, 1])
    with c1:
        st.selectbox("Persona" if modo_admin else "Tu nombre", opciones,
                     key="reg_eleccion", index=None,
                     placeholder="Escoge un nombre…")
        if st.session_state.get("reg_eleccion") == OTRA_PERSONA:
            st.text_input("Escribe el nombre completo", key="reg_otro")
        aviso = st.session_state.pop("reg_falta", None)
        if aviso:
            st.warning(aviso)
        st.button("Guardar" if modo_admin else "Guardar y entrar",
                  type="primary", key="reg_guardar",
                  on_click=_guardar_persona, args=(carpeta, modo_admin),
                  use_container_width=True)
        if modo_admin:
            st.button("Cancelar", key="reg_cancelar",
                      on_click=lambda: st.session_state.pop("reg_cambiando",
                                                            None),
                      use_container_width=True)
    if not modo_admin:
        st.caption(f"¿No apareces en la lista o este equipo es de un "
                   f"administrador? Pide que lo asignen en equipos.txt con el "
                   f"código {codigo_equipo()}.")
    if not carpeta:
        st.caption("No se encontró la carpeta «GMYA Tools» del Drive de la "
                   "firma en este equipo: la actividad se guarda en el "
                   "computador y se sube sola cuando la carpeta esté "
                   "disponible. Si ya existe, escribe aquí su ruta.")
        ruta = st.text_input("Ruta de la carpeta GMYA Tools (opcional)",
                             key="reg_ruta_manual",
                             placeholder=r"G:\Mi unidad\GMYA Tools")
        if ruta:
            ruta = ruta.strip().strip('"')
            if Path(ruta).is_dir() and not _es_carpeta_de_empresas(ruta):
                guardar_config(ruta_gmya_tools=ruta)
                st.session_state["reg_carpeta"] = ruta
                for llave in ("reg_persona", "reg_admin_de"):
                    st.session_state.pop(llave, None)
                st.success("Carpeta guardada. Recarga la página.")
            else:
                st.warning("Esa carpeta no existe en este equipo (o está "
                           "dentro de 001. EMPRESAS ACTIVAS, donde no se "
                           "escribe nada).")


def _cambiar_persona():
    # Solo se permite en equipos de administrador (se valida otra vez).
    if equipo_de_admin(st.session_state.get("reg_carpeta")):
        st.session_state["reg_cambiando"] = True


def tarjeta_persona_lateral(persona, carpeta):
    st.markdown(
        f'<div class="gm-side-nota" style="margin-top:.2rem">'
        f'<b>Equipo de:</b> {html.escape(persona)}<br>'
        f'<span style="opacity:.75">Código {codigo_equipo()}'
        + ("" if carpeta else " · registro sin conexión al Drive")
        + '</span></div>', unsafe_allow_html=True)
    if st.session_state.get("reg_equipo_admin"):
        st.button("Cambiar de usuario", key="reg_cambiar",
                  on_click=_cambiar_persona, use_container_width=True,
                  help="Solo en equipos de administrador.")


def modulo_uso():
    banner_modulo(
        "Administración",
        "Uso de la plataforma",
        "Quién usa la plataforma, qué módulos y con qué frecuencia, a partir "
        "de los registros de cada equipo en la carpeta «GMYA Tools» del "
        "Drive. Sirve para hablar con quien no la usa y entender por qué.",
        ("Registros por equipo", "Sin datos de clientes"))
    carpeta = st.session_state.get("reg_carpeta")
    if not carpeta:
        st.warning("No se encontró la carpeta «GMYA Tools» en este equipo.")
        return
    c1, c2 = st.columns([1, 2])
    with c1:
        dias = st.selectbox("Periodo", [7, 15, 30, 90, 365], index=2,
                            key="uso_dias",
                            format_func=lambda d: f"Últimos {d} días")
    with c2:
        alerta = st.slider("Marcar sin actividad desde (días)", 1, 30, 7,
                           key="uso_alerta")
    hoy = datetime.date.today()
    filas = leer_registros(carpeta, hoy - datetime.timedelta(days=dias))
    usuarios = leer_usuarios(carpeta)
    resumen = resumen_uso(filas, usuarios, hoy, alerta)

    titulo_seccion(
        "Resumen por persona", 1,
        "<b>Horas abierta</b>: tiempo con la plataforma abierta (se cuenta en "
        "bloques de 10 minutos). <b>Horas en uso</b>: bloques en los que hubo "
        "al menos un clic o carga. <b>Acciones</b>: clics, cargas, búsquedas "
        "y descargas. Arriba aparecen las personas sin actividad desde el "
        "número de días elegido (incluye las de usuarios.txt que nunca la "
        "han abierto).")
    sin_uso = [r["Persona"] for r in resumen if r["_alerta"]]
    m = st.columns(4)
    m[0].metric("Personas", len(resumen))
    m[1].metric("Sin actividad reciente", len(sin_uso))
    m[2].metric("Registros leídos", len(filas))
    m[3].metric("Errores", sum(1 for f in filas if f["evento"] == "error"))
    if sin_uso:
        st.warning("Sin actividad: " + ", ".join(sin_uso))
    st.dataframe([{k: v for k, v in r.items() if not k.startswith("_")}
                  for r in resumen], use_container_width=True,
                 hide_index=True)

    titulo_seccion(
        "Uso por módulo", 2,
        "Veces que se abrió cada módulo y archivos generados en el periodo.")
    por_modulo = Counter(MODULOS_NOMBRE.get(f["modulo"], f["modulo"])
                         for f in filas if f["evento"] == "módulo")
    if por_modulo:
        st.bar_chart({"Veces abierto": dict(por_modulo.most_common())},
                     horizontal=True)

    titulo_seccion(
        "Errores registrados", 3,
        "Cada vez que una pantalla mostró un error en rojo queda una línea "
        "aquí: quién, cuándo, en qué módulo, qué se estaba haciendo y qué "
        "significa. El texto no incluye nombres de archivos ni datos de "
        "clientes; la parte <b>en …</b> indica el lugar del código (sirve "
        "para corregirlo).")
    errores = sorted((f for f in filas if f["evento"] == "error"),
                     key=lambda f: (f["fecha"], f["hora"]), reverse=True)
    if not errores:
        st.success("Sin errores en el periodo.")
    else:
        tabla_errores = []
        for f in errores[:500]:
            accion, significado, hacer = explicar_error(f["detalle"])
            tabla_errores.append({
                "Fecha": f["fecha"], "Hora": f["hora"],
                "Persona": f.get("persona", ""),
                "Módulo": MODULOS_NOMBRE.get(f["modulo"], f["modulo"]),
                "Qué se hacía": accion or "—",
                "Qué significa": significado, "Qué hacer": hacer,
                "Mensaje registrado": f["detalle"],
                "Versión": f.get("version", "")})
        repetidos = Counter((t["Módulo"], t["Qué se hacía"])
                            for t in tabla_errores)
        st.caption("Más frecuentes: " + " · ".join(
            f"{m} / {a} ({n})" for (m, a), n in repetidos.most_common(3)))
        st.dataframe(tabla_errores, use_container_width=True,
                     hide_index=True, height=320,
                     column_config={
                         "Qué significa": st.column_config.TextColumn(
                             width="large"),
                         "Mensaje registrado": st.column_config.TextColumn(
                             width="large")})
        st.caption("Los errores de versiones anteriores a la v6.3.1 no "
                   "traen el lugar del código; desde la v6.3.1 sí.")

    titulo_seccion(
        "Detalle por persona", 4,
        "Línea de tiempo de una persona: módulos, acciones y errores (los "
        "errores ayudan a entender por qué no le sirve la herramienta).")
    personas = sorted({r["Persona"] for r in resumen}, key=comparable)
    if personas:
        quien = st.selectbox("Persona", personas, key="uso_persona")
        detalle = [f for f in filas if f.get("persona") == quien]
        detalle.sort(key=lambda f: (f["fecha"], f["hora"]), reverse=True)
        st.dataframe([{"Fecha": f["fecha"], "Hora": f["hora"],
                       "Módulo": MODULOS_NOMBRE.get(f["modulo"], f["modulo"]),
                       "Evento": f["evento"], "Detalle": f["detalle"],
                       "Interacciones": f["interacciones"],
                       "Equipo": f["equipo"]} for f in detalle[:500]],
                     use_container_width=True, hide_index=True, height=360)
    if filas:
        salida = io.StringIO()
        import csv
        escritor = csv.DictWriter(salida, fieldnames=COLUMNAS_REGISTRO,
                                  delimiter=";", extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)
        st.download_button(
            "Descargar registros del periodo (CSV)",
            salida.getvalue().encode("utf-8-sig"),
            file_name=f"GMYA uso {hoy:%Y-%m-%d}.csv", mime="text/csv",
            key="uso_descargar")
