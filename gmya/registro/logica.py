"""Usuario del equipo y registro de uso (sin Streamlit).

Contrato:
  carpeta_gmya() -> carpeta "GMYA Tools" del Drive (o None).
  leer_usuarios(carpeta) / leer_equipos(carpeta) -> personas y equipos
      (usuarios.txt: los marcados con * son administradores).
  es_admin(persona, carpeta) -> bool.
  escribir_registro(evento, detalle, ...) -> agrega una fila al CSV del dia.
  leer_registros / resumen_uso -> datos del modulo "Uso de la plataforma".
  explicar_error(texto) -> (que se hacia, que significa, que hacer) en
      lenguaje sencillo, para la pantalla y el panel de errores.
REGLA: el registro guarda solo modulo/accion/conteos; NUNCA datos de
clientes (nombres de archivos, NIT, valores). texto_seguro_registro lo
garantiza.

Depende de: gmya.config, gmya.comun.texto, gmya.comun.numeros, gmya.comun.config_equipo, gmya.modulos.busqueda.logica
"""

import datetime
import io
import re
from collections import Counter, defaultdict
from pathlib import Path

from gmya.config import VERSION
from gmya.comun.texto import comparable, decodificar
from gmya.comun.numeros import numero
from gmya.comun.config_equipo import guardar_config, leer_config
from gmya.modulos.busqueda.logica import (
    CLAVE_EMPRESAS, detectar_rutas_drive, NOMBRES_COMPARTIDAS, _subcarpetas,
)


# ============================================================
# REGISTRO DE USO POR EQUIPO (sin credenciales)
# ============================================================
# Cada computador se asigna una vez a una persona (no hay contrasena: se
# identifica el EQUIPO, no a quien esta sentado). La actividad se escribe
# en archivos CSV dentro de la carpeta compartida "GMYA Tools" del Drive
# de la firma, uno por equipo y por dia, para saber quien usa la
# plataforma y para que, y hablar con quien no le encuentra utilidad.
# No se registran datos de clientes: solo modulo, accion y cantidades.
#
# Carpeta "GMYA Tools" (en Mi unidad, como acceso directo, o en una unidad
# compartida):
#   usuarios.txt        una persona por linea; "*" al inicio = puede ver el
#                       panel "Uso de la plataforma"
#   equipos.txt         opcional: "<codigo de equipo> = Persona" para
#                       corregir a quien pertenece un equipo
#   Registros de uso/   AAAA-MM/AAAA-MM-DD Persona CODIGO.csv (los escribe
#                       la plataforma)
NOMBRES_CARPETA_GMYA = ("GMYA TOOLS",)
CARPETA_REGISTROS = "Registros de uso"
ARCHIVO_USUARIOS = "usuarios.txt"
ARCHIVO_EQUIPOS = "equipos.txt"
CARPETA_PENDIENTES = Path.home() / ".gmya" / "registros_pendientes"
COLUMNAS_REGISTRO = ["fecha", "hora", "persona", "equipo", "nombre_equipo",
                     "version", "sesion", "modulo", "evento", "detalle",
                     "interacciones"]
MINUTOS_LATIDO = 10


def id_equipo():
    """Identificador estable del computador (MachineGuid de Windows)."""
    import os
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography", 0,
                    winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
            ) as llave:
                valor, _ = winreg.QueryValueEx(llave, "MachineGuid")
                if valor:
                    return str(valor).lower()
        except Exception:
            pass
    for ruta in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            texto = Path(ruta).read_text().strip()
            if texto:
                return texto.lower()
        except Exception:
            continue
    config = leer_config()
    if not config.get("id_equipo_local"):
        import uuid
        guardar_config(id_equipo_local=str(uuid.uuid4()))
        config = leer_config()
    return config.get("id_equipo_local") or "sin-id"


def codigo_equipo(ident=None):
    """Codigo corto y legible del equipo (8 caracteres)."""
    return re.sub(r"[^0-9A-Za-z]", "", ident or id_equipo())[:8].upper()


def nombre_equipo():
    import platform
    return platform.node() or ""


def _es_carpeta_de_empresas(ruta):
    return CLAVE_EMPRESAS in comparable(str(ruta))


def detectar_carpeta_gmya(mi_unidad=None):
    """
    Carpeta "GMYA Tools" en Mi unidad (carpeta o acceso directo, hasta dos
    niveles) o en Unidades compartidas (la unidad misma o una carpeta
    dentro). Nunca dentro de 001. EMPRESAS ACTIVAS.
    """
    raices = []
    if mi_unidad:
        raices.append(Path(mi_unidad))
    else:
        config = leer_config()
        if config.get("ruta_drive"):
            raices.append(Path(config["ruta_drive"]))
        raices += [Path(r) for r in detectar_rutas_drive()]

    def es_gmya(ruta):
        return comparable(Path(ruta).name) in NOMBRES_CARPETA_GMYA and \
            not _es_carpeta_de_empresas(ruta)

    bases = []
    for raiz in raices:
        bases.append(raiz)
        for nombre in NOMBRES_COMPARTIDAS:
            bases.append(raiz.parent / nombre)
    vistas = set()
    for base in bases:
        if str(base) in vistas:
            continue
        vistas.add(str(base))
        try:
            if not base.is_dir():
                continue
        except OSError:
            continue
        nivel1 = _subcarpetas(base)
        for sub in nivel1:
            if es_gmya(sub):
                return str(sub)
        for sub in nivel1:
            if _es_carpeta_de_empresas(sub):
                continue
            for sub2 in _subcarpetas(sub):
                if es_gmya(sub2):
                    return str(sub2)
    return ""


def carpeta_gmya(forzar=False):
    """Ruta de "GMYA Tools" (guardada en la configuracion del equipo)."""
    config = leer_config()
    ruta = config.get("ruta_gmya_tools") or ""
    try:
        if ruta and Path(ruta).is_dir() and not _es_carpeta_de_empresas(ruta):
            return ruta
    except OSError:
        pass
    if not forzar and config.get("_gmya_tools_buscada_hoy") == \
            datetime.date.today().isoformat():
        return ""
    ruta = detectar_carpeta_gmya()
    guardar_config(ruta_gmya_tools=ruta,
                   _gmya_tools_buscada_hoy=datetime.date.today().isoformat())
    return ruta


def leer_usuarios(carpeta):
    """[(nombre, es_admin)] de usuarios.txt ("*" al inicio = admin)."""
    if not carpeta:
        return []
    ruta = Path(carpeta) / ARCHIVO_USUARIOS
    try:
        lineas = decodificar(ruta.read_bytes()).splitlines()
    except Exception:
        return []
    usuarios = []
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        admin = linea.startswith("*")
        nombre = linea.lstrip("*").strip()
        if nombre:
            usuarios.append((nombre, admin))
    return usuarios


def leer_equipos(carpeta):
    """{codigo de equipo: persona} de equipos.txt."""
    if not carpeta:
        return {}
    try:
        lineas = decodificar((Path(carpeta) / ARCHIVO_EQUIPOS)
                             .read_bytes()).splitlines()
    except Exception:
        return {}
    equipos = {}
    for linea in lineas:
        if "=" not in linea or linea.strip().startswith("#"):
            continue
        codigo, persona = linea.split("=", 1)
        codigo = re.sub(r"[^0-9A-Za-z]", "", codigo).upper()
        if codigo and persona.strip():
            equipos[codigo[:8]] = persona.strip()
    return equipos


def nombres_admin(carpeta):
    return {comparable(n) for n, admin in leer_usuarios(carpeta) if admin}


def equipo_de_admin(carpeta):
    """True si equipos.txt asigna este computador a un administrador. Solo
    en esos equipos se puede cambiar de usuario."""
    asignada = leer_equipos(carpeta).get(codigo_equipo())
    return bool(asignada) and comparable(asignada) in nombres_admin(carpeta)


def persona_del_equipo(carpeta=None):
    """
    Persona de este computador:
    - equipos.txt manda (asi se asignan los equipos de los administradores);
    - en un equipo de administrador, la persona que el administrador eligio
      con "Cambiar de usuario";
    - si no, la que se eligio la primera vez, siempre que NO sea un
      administrador (un administrador solo se asigna desde equipos.txt).
    """
    asignada = leer_equipos(carpeta).get(codigo_equipo())
    admins = nombres_admin(carpeta)
    config = leer_config()
    elegida = (config.get("persona") or "").strip()
    if asignada:
        if comparable(asignada) in admins and config.get("persona_por_admin") \
                and elegida:
            return elegida
        return asignada
    if elegida and comparable(elegida) in admins:
        return ""
    return elegida


def asignar_persona(nombre, por_admin=False):
    guardar_config(persona=str(nombre).strip(), persona_por_admin=por_admin,
                   persona_desde=datetime.datetime.now().isoformat(
                       timespec="seconds"))


def es_admin(persona, carpeta):
    return bool(persona) and comparable(persona) in nombres_admin(carpeta)


def _nombre_archivo_registro(persona, momento):
    persona_segura = re.sub(r'[<>:"/\\|?*]', "", persona).strip() or \
        "SIN PERSONA"
    return (f"{momento:%Y-%m}", f"{momento:%Y-%m-%d} {persona_segura} "
                                f"{codigo_equipo()}.csv")


def _linea_csv(valores):
    salida = io.StringIO()
    import csv
    csv.writer(salida, delimiter=";", lineterminator="\r\n").writerow(
        valores)
    return salida.getvalue()


def _anexar(ruta, texto):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with open(ruta, "a", encoding="utf-8-sig" if nuevo else "utf-8",
              newline="") as archivo:
        if nuevo:
            archivo.write(_linea_csv(COLUMNAS_REGISTRO))
        archivo.write(texto)


def _vaciar_pendientes(carpeta):
    """Copia al Drive lo que se registro sin conexion."""
    if not carpeta or not CARPETA_PENDIENTES.is_dir():
        return
    for archivo in sorted(CARPETA_PENDIENTES.glob("*/*.csv")):
        try:
            lineas = archivo.read_text(encoding="utf-8-sig").splitlines(
                keepends=True)[1:]
            destino = Path(carpeta) / CARPETA_REGISTROS / \
                archivo.parent.name / archivo.name
            if lineas:
                _anexar(destino, "".join(lineas))
            archivo.unlink()
        except Exception:
            continue


def escribir_registro(evento, detalle="", modulo="", persona="", sesion="",
                      interacciones="", carpeta=None, momento=None):
    """
    Agrega una linea al registro del dia. Si la carpeta del Drive no esta
    disponible se guarda en el equipo y se copia la proxima vez.
    Devuelve True si quedo en el Drive.
    """
    momento = momento or datetime.datetime.now()
    carpeta = carpeta if carpeta is not None else carpeta_gmya()
    persona = persona or persona_del_equipo(carpeta) or "SIN PERSONA"
    detalle = re.sub(r"[\r\n;]+", " ", str(detalle or ""))[:200]
    linea = _linea_csv([f"{momento:%Y-%m-%d}", f"{momento:%H:%M:%S}",
                        persona, codigo_equipo(), nombre_equipo(), VERSION,
                        sesion, modulo, evento, detalle, interacciones])
    mes, nombre = _nombre_archivo_registro(persona, momento)
    if carpeta and not _es_carpeta_de_empresas(carpeta):
        try:
            _vaciar_pendientes(carpeta)
            _anexar(Path(carpeta) / CARPETA_REGISTROS / mes / nombre, linea)
            return True
        except Exception:
            pass
    try:
        _anexar(CARPETA_PENDIENTES / mes / nombre, linea)
    except Exception:
        pass
    return False


def texto_seguro_registro(texto, limite=90):
    """Quita del texto lo que pueda identificar documentos o clientes
    (comillas, rutas y nombres de archivo)."""
    texto = re.sub(r"<[^>]+>", "", str(texto or ""))
    texto = re.sub(r"[«\"'“][^»\"'”]*[»\"'”]", "«…»", texto)
    texto = re.sub(r"[A-Za-z]:\\\S+|/\S+/\S+", "…", texto)
    texto = re.sub(r"\S+\.(xlsx?|pdf|txt|zip|csv|xml)\b", "archivo .\\1",
                   texto, flags=re.I)
    return re.sub(r"\s+", " ", texto).strip()[:limite]


def leer_registros(carpeta, desde=None):
    """Lineas de todos los registros (lista de dicts) desde una fecha."""
    base = Path(carpeta) / CARPETA_REGISTROS if carpeta else None
    filas = []
    if not base or not base.is_dir():
        return filas
    import csv
    for archivo in sorted(base.glob("*/*.csv")):
        try:
            fecha_archivo = datetime.date.fromisoformat(archivo.name[:10])
        except ValueError:
            fecha_archivo = None
        if desde and fecha_archivo and fecha_archivo < desde:
            continue
        try:
            texto = archivo.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for fila in csv.DictReader(io.StringIO(texto), delimiter=";"):
            if fila.get("fecha"):
                filas.append(fila)
    return filas


def resumen_uso(filas, usuarios, hoy=None, dias_alerta=7):
    """Resumen por persona para el panel de uso."""
    hoy = hoy or datetime.date.today()
    por_persona = defaultdict(list)
    for f in filas:
        por_persona[f.get("persona") or "SIN PERSONA"].append(f)
    nombres = [n for n, _ in usuarios]
    for n in nombres:
        por_persona.setdefault(n, [])
    salida = []
    for persona, lista in por_persona.items():
        lista.sort(key=lambda f: (f["fecha"], f["hora"]))
        latidos = [f for f in lista if f["evento"] == "abierta"]
        activos = [f for f in latidos if (numero(f.get("interacciones"))
                                         or 0) > 0]
        acciones = [f for f in lista if f["evento"] in
                    ("clic", "descarga", "carga", "búsqueda", "abrir")]
        generados = [f for f in lista if f["evento"] == "descarga" or (
            f["evento"] == "clic" and re.match(
                r"(GENERAR|PROCESAR)", comparable(f["detalle"])))]
        modulos = Counter(f["modulo"] for f in lista
                          if f["evento"] in ("módulo",) and f["modulo"])
        ultima = lista[-1] if lista else None
        ultima_fecha = datetime.date.fromisoformat(ultima["fecha"]) \
            if ultima else None
        dias_sin = (hoy - ultima_fecha).days if ultima_fecha else None
        salida.append({
            "Persona": persona,
            "Última actividad": f"{ultima['fecha']} {ultima['hora'][:5]}"
            if ultima else "Nunca",
            "Días sin usarla": dias_sin if dias_sin is not None else "—",
            "Días con uso": len({f["fecha"] for f in lista}),
            "Sesiones": len({f["sesion"] for f in lista if f["sesion"]}),
            "Horas abierta": round(len(latidos) * MINUTOS_LATIDO / 60, 1),
            "Horas en uso": round(len(activos) * MINUTOS_LATIDO / 60, 1),
            "Acciones": len(acciones),
            "Archivos generados": len(generados),
            "Errores": sum(1 for f in lista if f["evento"] == "error"),
            "Módulos más usados": ", ".join(
                f"{MODULOS_NOMBRE.get(m, m)} ({n})"
                for m, n in modulos.most_common(3)),
            "Equipos": ", ".join(sorted({f["equipo"] for f in lista
                                         if f.get("equipo")})),
            "_alerta": dias_sin is None or dias_sin >= dias_alerta,
        })
    salida.sort(key=lambda r: (not r["_alerta"], comparable(r["Persona"])))
    return salida


# Nombres de los modulos para los registros (los mismos del menu).
MODULOS_NOMBRE = {"inicio": "Inicio", "busqueda": "Búsqueda de archivos",
                  "planillas": "Planillas", "bancos": "Conciliación bancaria",
                  "dian": "Conciliación DIAN", "pagos": "Programación de pagos",
                  "odoo": "Automatizaciones Odoo",
                  "nomina": "Pagos de nómina",
                  "uso": "Uso de la plataforma",
                  "reporte": "Reportar un error"}


# ------------------------------------------------------------
# Errores: explicacion en lenguaje sencillo (v6.3.1)
# ------------------------------------------------------------
# Cada regla: (patron en el texto del error, que significa, que hacer).
# Se revisan en orden; la primera que coincide gana. Sirve para los errores
# que se muestran en pantalla y para los ya guardados en el registro.
EXPLICACION_ERRORES = [
    (r"Permission|denegado|being used|siendo utilizado|PermissionError",
     "El archivo estaba abierto en otro programa (Excel) o Windows no dio "
     "permiso para leerlo.",
     "Cerrar el archivo en Excel y volver a intentarlo."),
    (r"BadZipFile|not a zip|zip file|InvalidFileException",
     "El archivo no es un Excel .xlsx válido: está dañado, protegido con "
     "contraseña o es otro formato con extensión .xlsx.",
     "Abrirlo en Excel, quitar la contraseña si tiene y guardarlo de nuevo "
     "como Libro de Excel (.xlsx)."),
    (r"PDFSyntax|PdfminerException|No /Root|EOF marker|PSEOF|password|"
     r"contraseña|cifrad|encrypt",
     "El PDF está dañado, protegido con contraseña o es una imagen "
     "escaneada sin texto.",
     "Descargar el PDF de nuevo desde el origen (banco, HELISA, DIAN). Si "
     "es escaneado, pedir la versión digital."),
    (r"xlrd|LibreOffice|Excel 97|BIFF|CompDoc",
     "No se pudo leer un Excel antiguo (.xls).",
     "Abrirlo en Excel y guardarlo como .xlsx, o volver a exportarlo desde "
     "HELISA."),
    (r"MemoryError|memoria",
     "El equipo se quedó sin memoria con archivos muy grandes.",
     "Cerrar otros programas o cargar menos archivos a la vez."),
    (r"No existe esa carpeta|No such file|FileNotFound|Errno 2",
     "Una carpeta o archivo indicado no existe en este equipo (o el Drive "
     "no está sincronizado).",
     "Revisar la ruta y que Google Drive esté abierto y sincronizado."),
    (r"KeyError|IndexError|TypeError|AttributeError|NoneType|list index|"
     r"not subscriptable|unsupported operand|object has no attribute",
     "El documento tiene una estructura distinta a la esperada (columnas, "
     "títulos o filas que la plataforma no reconoce) o es un caso que la "
     "plataforma todavía no maneja. No es un error de la persona.",
     "Avisar al administrador con el módulo, la fecha y la hora para "
     "revisar el caso; el detalle técnico indica en qué parte del código "
     "ocurrió."),
    (r"ValueError|could not convert|invalid literal|time data|"
     r"does not match format",
     "Un valor del documento (fecha, número o código) vino en un formato "
     "que la plataforma no reconoce.",
     "Revisar que el archivo sea el informe correcto; si lo es, avisar al "
     "administrador para ajustar la lectura."),
]

ACCIONES_ERROR = [
    (r"generar la conciliaci[oó]n DIAN", "Generar la conciliación DIAN"),
    (r"generar la conciliaci[oó]n", "Generar la conciliación bancaria"),
    (r"generar el archivo", "Generar el Excel de salida"),
    (r"leer la base de datos", "Leer la base de datos de nómina"),
    (r"planilla de n[oó]mina", "Leer la planilla de nómina (PDF)"),
    (r"informe de vacaciones", "Leer el informe de vacaciones (PDF)"),
    (r"formato de pagos", "Leer el formato de pagos del banco"),
    (r"leer los archivos|leer los documentos", "Leer los archivos cargados"),
    (r"explorador|abrir", "Abrir un archivo o carpeta del Drive"),
]


def explicar_error(texto):
    """(accion, que_significa, que_hacer) en lenguaje sencillo para el
    texto de un error (de pantalla o del registro)."""
    texto = str(texto or "")
    accion = next((a for p, a in ACCIONES_ERROR
                   if re.search(p, texto, re.I)), "")
    tipo = re.search(r"·\s*([A-Z]\w+): ", texto) or re.search(
        r"\b(\w+(?:Error|Exception|File|Operation))\b: ", texto)
    cola = texto[tipo.end():] if tipo else texto.split(": ", 1)[-1]
    cola = cola.split(" · en ")[0]
    if (not tipo or tipo.group(1) == "ValueError") and re.search(
            r"[áéíóúñ¿]|\b(no se|falta|debe|revisa|carga|exporta)\b",
            cola, re.I):
        return (accion, "La plataforma reconoció el problema y lo explica "
                        "en el mensaje (archivo equivocado, columnas o datos "
                        "que faltan).",
                "Leer el mensaje registrado y revisar el archivo cargado.")
    for patron, significado, hacer in EXPLICACION_ERRORES:
        if re.search(patron, texto, re.I):
            return accion, significado, hacer
    return (accion, "Error no clasificado.",
            "Avisar al administrador con el módulo, la fecha y la hora.")
