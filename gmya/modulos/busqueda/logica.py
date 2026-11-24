"""Busqueda de archivos en Google Drive (sin Streamlit).

Contrato:
  detectar_rutas_drive() -> rutas candidatas de "Mi unidad" en el equipo.
  IndiceDrive(raiz) -> indice en segundo plano (proceso aparte de prioridad
      baja; en el .exe usa un hilo). buscar_en_indice(...) -> resultados.
  abrir_en_sistema(ruta) -> abre el archivo/carpeta con el programa del SO.
REGLA: la carpeta "001. EMPRESAS ACTIVAS USO DIARIO" es SOLO LECTURA: nada
de este modulo escribe ahi (el indice vive en ~/.gmya).

Depende de: gmya.comun.texto
"""

import datetime
import sys
from collections import OrderedDict
from pathlib import Path

from gmya.comun.texto import comparable


# ============================================================
# BUSQUEDA DE ARCHIVOS EN GOOGLE DRIVE (MI UNIDAD) - v4.8
# ============================================================
# La plataforma corre en el equipo del usuario: se recorre la carpeta
# "Mi unidad" de Google Drive para escritorio (p. ej. G:\Mi unidad) y, en
# especial, la carpeta de trabajo diario "001. EMPRESAS ACTIVAS USO
# DIARIO" (una subcarpeta por empresa). Se busca por nombre con filtros
# (empresa, tipo, fecha) y se muestra un explorador por tarjetas. Un clic
# abre el archivo con su programa o la carpeta en el Explorador de
# Windows. Solo lectura: nunca se crea, mueve ni borra nada en el Drive.
NOMBRES_MI_UNIDAD = ("Mi unidad", "My Drive", "Meine Ablage", "Mon Drive")
NOMBRES_COMPARTIDAS = ("Unidades compartidas", "Shared drives")
CLAVE_EMPRESAS = "EMPRESAS ACTIVAS"          # 001. EMPRESAS ACTIVAS USO DIARIO


MAX_ELEMENTOS_CARPETA = 400       # elementos que se muestran por carpeta
MAX_RESULTADOS = 300              # resultados que se muestran
MAX_ENTRADAS_INDICE = 400000      # tope de seguridad del indice
IGNORAR_DRIVE = {".tmp.drivedownload", ".tmp.driveupload", "desktop.ini",
                 "thumbs.db", ".ds_store", "$recycle.bin",
                 "system volume information"}

# Filtro por tipo: etiqueta -> extensiones ("Carpetas" es especial).
TIPOS_ARCHIVO = OrderedDict([
    ("Carpetas", None),
    ("Excel", {"xls", "xlsx", "xlsm", "xlsb", "csv", "ods"}),
    ("PDF", {"pdf"}),
    ("Word", {"doc", "docx", "odt", "rtf"}),
    ("Imágenes", {"png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff",
                  "heic", "webp"}),
    ("XML / TXT", {"xml", "txt", "json"}),
    ("Comprimidos", {"zip", "rar", "7z"}),
    ("Google (Docs, Hojas)", {"gdoc", "gsheet", "gslides", "gform"}),
])
FECHAS_FILTRO = OrderedDict([
    ("Cualquier fecha", None),
    ("Últimos 7 días", 7),
    ("Últimos 30 días", 30),
    ("Últimos 90 días", 90),
    ("Este año", "anio"),
    ("Año anterior", "anio_anterior"),
])
ORDEN_RESULTADOS = ["Relevancia", "Más reciente primero", "Nombre (A-Z)"]


def detectar_rutas_drive():
    """Ubicaciones habituales de 'Mi unidad' (Drive para escritorio)."""
    import os
    import string
    candidatas = []
    if os.name == "nt":
        for letra in string.ascii_uppercase[2:]:
            raiz = Path(f"{letra}:\\")
            try:
                if not raiz.exists():
                    continue
            except OSError:
                continue
            for nombre in NOMBRES_MI_UNIDAD:
                candidatas.append(raiz / nombre)
    casa = Path.home()
    for nombre in NOMBRES_MI_UNIDAD:
        candidatas.append(casa / "Google Drive" / nombre)
    candidatas.append(casa / "Google Drive")
    nube = casa / "Library" / "CloudStorage"            # macOS
    try:
        for carpeta in nube.glob("GoogleDrive-*"):
            for nombre in NOMBRES_MI_UNIDAD:
                candidatas.append(carpeta / nombre)
    except OSError:
        pass
    encontradas = []
    for ruta in candidatas:
        try:
            if ruta.is_dir() and str(ruta) not in encontradas:
                encontradas.append(str(ruta))
        except OSError:
            continue
    return encontradas


def validar_ruta_drive(texto):
    """(ruta Path o None, mensaje, nivel) nivel: ok / aviso / error."""
    texto = str(texto or "").strip().strip('"').strip("'")
    if not texto:
        return None, "Escribe la ruta de la carpeta «Mi unidad».", "error"
    ruta = Path(texto).expanduser()
    try:
        if not ruta.exists():
            return None, f"No existe la carpeta «{texto}» en este equipo.", \
                "error"
        if not ruta.is_dir():
            return None, "La ruta indicada es un archivo, no una carpeta.", \
                "error"
    except OSError as error:
        return None, f"No se pudo leer la ruta: {error}", "error"
    if ruta.name not in NOMBRES_MI_UNIDAD:
        return ruta, ("La carpeta no se llama «Mi unidad». Se usará igual; "
                      "verifica que sea la raíz de tu Google Drive."), "aviso"
    return ruta, "Ruta de Mi unidad válida.", "ok"


def _ignorar(nombre):
    return nombre.lower() in IGNORAR_DRIVE or nombre.startswith("~$")


def _subcarpetas(ruta):
    import os
    try:
        with os.scandir(ruta) as entradas:
            return [e.path for e in entradas if not _ignorar(e.name)
                    and e.is_dir(follow_symlinks=False)]
    except OSError:
        return []


def detectar_carpeta_empresas(mi_unidad, profundidad=3):
    """
    Busca la carpeta '001. EMPRESAS ACTIVAS USO DIARIO' (o cualquiera que
    contenga 'EMPRESAS ACTIVAS') en Mi unidad y en Unidades compartidas,
    por niveles y sin bajar mas de 'profundidad'.
    """
    mi_unidad = Path(mi_unidad)
    raices = [mi_unidad]
    for nombre in NOMBRES_COMPARTIDAS:
        raices.append(mi_unidad.parent / nombre)
    encontradas = []
    for raiz in raices:
        nivel = [str(raiz)]
        for _ in range(profundidad):
            siguiente = []
            for carpeta in nivel:
                for sub in _subcarpetas(carpeta):
                    if CLAVE_EMPRESAS in comparable(Path(sub).name):
                        encontradas.append(sub)
                    else:
                        siguiente.append(sub)
            nivel = siguiente[:2000]
        if encontradas:
            break
    encontradas.sort(key=lambda r: (not Path(r).name.startswith("001"),
                                    len(r)))
    return encontradas


def listar_empresas(carpeta_empresas):
    """Subcarpetas de la carpeta de empresas (una por empresa)."""
    return sorted(((Path(r).name, r) for r in _subcarpetas(carpeta_empresas)),
                  key=lambda x: x[0].casefold())


def extension(nombre):
    punto = nombre.rfind(".")
    return nombre[punto + 1:].lower() if punto > 0 else ""


def tipo_de(nombre, es_dir):
    if es_dir:
        return "Carpetas"
    ext = extension(nombre)
    for etiqueta, extensiones in TIPOS_ARCHIVO.items():
        if extensiones and ext in extensiones:
            return etiqueta
    return "Otros"


def listar_carpeta(ruta, limite=MAX_ELEMENTOS_CARPETA):
    """
    (carpetas, archivos, ocultos): cada elemento
    {n, r, d, m (fecha de modificacion), t (tamano)}.
    """
    import os
    elementos = []
    try:
        with os.scandir(ruta) as entradas:
            for e in entradas:
                if _ignorar(e.name):
                    continue
                try:
                    es_dir = e.is_dir(follow_symlinks=False)
                    info = e.stat(follow_symlinks=False)
                    mtime, tam = info.st_mtime, info.st_size
                except OSError:
                    es_dir, mtime, tam = False, 0, 0
                elementos.append({"n": e.name, "r": e.path, "d": es_dir,
                                  "m": mtime, "t": 0 if es_dir else tam})
    except OSError:
        return [], [], 0
    carpetas = sorted([x for x in elementos if x["d"]],
                      key=lambda x: x["n"].casefold())
    archivos = sorted([x for x in elementos if not x["d"]],
                      key=lambda x: x["n"].casefold())
    total = len(carpetas) + len(archivos)
    carpetas = carpetas[:limite]
    archivos = archivos[:max(0, limite - len(carpetas))]
    return carpetas, archivos, total - len(carpetas) - len(archivos)


def _leer_directorio(ruta, primer):
    """Una carpeta: (entradas, subcarpetas[(ruta, nivel1)], error)."""
    import os
    entradas, subcarpetas = [], []
    try:
        with os.scandir(ruta) as lista:
            for e in lista:
                if _ignorar(e.name):
                    continue
                try:
                    es_dir = e.is_dir(follow_symlinks=False)
                    info = e.stat(follow_symlinks=False)
                    mtime, tam = info.st_mtime, info.st_size
                except OSError:
                    es_dir, mtime, tam = False, 0, 0
                nivel1 = primer or (e.name if es_dir else "")
                entradas.append((e.path, e.name, comparable(e.name), es_dir,
                                 mtime, tam, nivel1, comparable(nivel1),
                                 tipo_de(e.name, es_dir)))
                if es_dir:
                    subcarpetas.append((e.path, nivel1))
    except OSError:
        return entradas, subcarpetas, True
    return entradas, subcarpetas, False


def indexar_drive(raiz, limite=MAX_ENTRADAS_INDICE, hilos=16, destino=None,
                  avance=None):
    """
    Recorre toda la carpeta EN PARALELO (Google Drive para escritorio
    responde cada carpeta con latencia de red: leer 16 a la vez es mucho
    mas rapido que una por una). Devuelve (entradas, completo) con
    entradas = [(ruta, nombre, nombre_cmp, es_carpeta, mtime, tamano,
    primer_nivel, primer_nivel_cmp, tipo)].
    destino: lista donde ir agregando (para buscar mientras se indexa).
    avance: funcion(n_elementos, n_carpetas) para mostrar el progreso.
    """
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
    entradas = destino if destino is not None else []
    completo, carpetas = True, 0
    with ThreadPoolExecutor(max_workers=hilos) as grupo:
        pendientes = {grupo.submit(_leer_directorio, str(raiz), "")}
        while pendientes:
            hechos, pendientes = wait(pendientes, return_when=FIRST_COMPLETED)
            for futuro in hechos:
                nuevas, subcarpetas, error = futuro.result()
                carpetas += 1
                completo = completo and not error
                entradas.extend(nuevas)
                if len(entradas) >= limite:
                    for f in pendientes:
                        f.cancel()
                    return entradas, False
                for ruta, nivel1 in subcarpetas:
                    pendientes.add(grupo.submit(_leer_directorio, ruta,
                                                nivel1))
            if avance:
                avance(len(entradas), carpetas)
    return entradas, completo


# Indexador que corre en un PROCESO aparte (con prioridad baja): leer todo
# el Drive con hilos dentro de la plataforma compite con la interfaz (el
# GIL de Python) y la vuelve lenta. Se escribe a ~/.gmya/indexador.py y se
# ejecuta con el mismo Python; deja el indice en el mismo .pkl.
CODIGO_INDEXADOR = r"""
import datetime, json, os, pickle, re, sys, time, unicodedata
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

with open(sys.argv[1], encoding="utf-8") as f:
    P = json.load(f)
IGNORAR = set(P["ignorar"])
TIPOS = P["tipos"]


def comparable(t):
    t = unicodedata.normalize("NFD", str(t or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().upper()


def tipo_de(nombre, es_dir):
    if es_dir:
        return "Carpetas"
    p = nombre.rfind(".")
    ext = nombre[p + 1:].lower() if p > 0 else ""
    for etiqueta, extensiones in TIPOS:
        if extensiones and ext in extensiones:
            return etiqueta
    return "Otros"


def leer(ruta, primer):
    entradas, subs = [], []
    try:
        with os.scandir(ruta) as lista:
            for e in lista:
                if e.name.lower() in IGNORAR or e.name.startswith("~$"):
                    continue
                try:
                    es_dir = e.is_dir(follow_symlinks=False)
                    info = e.stat(follow_symlinks=False)
                    mtime, tam = info.st_mtime, info.st_size
                except OSError:
                    es_dir, mtime, tam = False, 0, 0
                n1 = primer or (e.name if es_dir else "")
                entradas.append((e.path, e.name, comparable(e.name), es_dir,
                                 mtime, tam, n1, comparable(n1),
                                 tipo_de(e.name, es_dir)))
                if es_dir:
                    subs.append((e.path, n1))
    except OSError:
        return entradas, subs, True
    return entradas, subs, False


entradas, completo, ultimo = [], True, 0.0
with ThreadPoolExecutor(max_workers=P["hilos"]) as grupo:
    pend = {grupo.submit(leer, P["raiz"], "")}
    while pend:
        hechos, pend = wait(pend, return_when=FIRST_COMPLETED)
        for fut in hechos:
            nuevas, subs, error = fut.result()
            completo = completo and not error
            entradas.extend(nuevas)
            for ruta, n1 in subs:
                pend.add(grupo.submit(leer, ruta, n1))
        if len(entradas) >= P["limite"]:
            for f in pend:
                f.cancel()
            completo = False
            break
        if time.time() - ultimo > 1:
            ultimo = time.time()
            try:
                with open(P["progreso"], "w") as f:
                    f.write(str(len(entradas)))
            except OSError:
                pass
tmp = P["destino"] + ".tmp"
with open(tmp, "wb") as f:
    pickle.dump({"version": 2, "raiz": P["raiz"], "entradas": entradas,
                 "completo": completo, "fecha": datetime.datetime.now()},
                f, protocol=pickle.HIGHEST_PROTOCOL)
os.replace(tmp, P["destino"])
"""


class IndiceDrive:
    """
    Indice de una carpeta del Drive que vive en memoria (compartido entre
    recargas de la pagina) y en disco (~/.gmya/indices), para que la busqueda
    sea inmediata incluso al abrir de nuevo la plataforma. Se actualiza en
    segundo plano: en un PROCESO aparte de prioridad baja (no hace lenta la
    interfaz) mientras se sigue buscando con el indice anterior. Solo la
    primera vez, si se esta en el buscador, se lee con hilos para poder
    buscar con lo que ya se haya leido.
    """
    VIGENCIA = 30 * 60                       # segundos antes de refrescar

    def __init__(self, raiz):
        import threading
        self.raiz = str(raiz)
        self.entradas = []
        self.completo = True
        self.fecha = None                    # datetime del ultimo indice
        self.parcial = []                    # lo leido en la construccion
        self._construyendo = False
        self._proceso = None
        self._leidos = 0
        self.error = None
        self._candado = threading.Lock()
        self._memo = None                    # ultima busqueda (clave, res)
        self._cargar_disco()

    # -- disco --
    def _archivo(self):
        import hashlib
        clave = hashlib.sha1(self.raiz.encode("utf-8")).hexdigest()[:16]
        return Path.home() / ".gmya" / "indices" / f"{clave}.pkl"

    def _cargar_disco(self):
        import pickle
        try:
            with open(self._archivo(), "rb") as archivo:
                datos = pickle.load(archivo)
            if datos.get("raiz") == self.raiz and datos.get("version") == 2:
                self.entradas = datos["entradas"]
                self.completo = datos["completo"]
                self.fecha = datos["fecha"]
                self._memo = None
                return True
        except Exception:
            pass
        return False

    def _guardar_disco(self):
        import pickle
        try:
            destino = self._archivo()
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_suffix(".tmp")
            with open(temporal, "wb") as archivo:
                pickle.dump({"version": 2, "raiz": self.raiz,
                             "entradas": self.entradas,
                             "completo": self.completo, "fecha": self.fecha},
                            archivo, protocol=pickle.HIGHEST_PROTOCOL)
            temporal.replace(destino)
        except Exception:
            pass

    # -- estado --
    @property
    def construyendo(self):
        self._revisar_proceso()
        return self._construyendo

    @property
    def leidos(self):
        if self._proceso is not None:
            try:
                return int(self._progreso().read_text() or 0)
            except Exception:
                return self._leidos
        return self._leidos

    def _progreso(self):
        return self._archivo().with_suffix(".progreso")

    def _revisar_proceso(self):
        """Si el proceso indexador ya termino, carga el indice nuevo."""
        proceso = self._proceso
        if proceso is None or proceso.poll() is None:
            return
        self._proceso = None
        if proceso.returncode == 0 and self._cargar_disco():
            self.error = None
        else:
            self.error = "no se pudo actualizar el índice"
        self._construyendo = False

    # -- construccion en segundo plano --
    def actualizar(self, forzar=False, interactivo=False):
        """
        Inicia la actualizacion si hace falta. True si quedo en curso.
        interactivo: el usuario esta en el buscador (la primera vez se lee
        con hilos para mostrar resultados mientras se lee).
        """
        import threading
        with self._candado:
            if self.construyendo:
                return True
            vencido = self.fecha is None or (
                datetime.datetime.now() - self.fecha).total_seconds() \
                > self.VIGENCIA
            if not (forzar or vencido):
                return False
            self._construyendo, self.parcial, self._leidos = True, [], 0
            if not (interactivo and not self.entradas) and \
                    self._lanzar_proceso():
                return True
        threading.Thread(target=self._construir, daemon=True,
                         name="gmya-indice").start()
        return True

    def _lanzar_proceso(self):
        """Indexa en un proceso aparte de prioridad baja. False si no se
        puede (p. ej. en el ejecutable empaquetado)."""
        import json
        import os
        import subprocess
        if getattr(sys, "frozen", False):
            return False
        try:
            carpeta = Path.home() / ".gmya"
            carpeta.mkdir(parents=True, exist_ok=True)
            script = carpeta / "indexador.py"
            if not script.exists() or script.read_text(
                    encoding="utf-8") != CODIGO_INDEXADOR:
                script.write_text(CODIGO_INDEXADOR, encoding="utf-8")
            self._archivo().parent.mkdir(parents=True, exist_ok=True)
            parametros = self._archivo().with_suffix(".json")
            parametros.write_text(json.dumps({
                "raiz": self.raiz, "destino": str(self._archivo()),
                "progreso": str(self._progreso()),
                "limite": MAX_ENTRADAS_INDICE, "hilos": 8,
                "ignorar": sorted(IGNORAR_DRIVE),
                "tipos": [[k, sorted(v) if v else None]
                          for k, v in TIPOS_ARCHIVO.items()],
            }), encoding="utf-8")
            opciones = {}
            if os.name == "nt":
                opciones["creationflags"] = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS",
                              0x00004000))
            else:
                opciones["preexec_fn"] = lambda: os.nice(10)
            self._proceso = subprocess.Popen(
                [sys.executable, str(script), str(parametros)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **opciones)
            return True
        except Exception:
            self._proceso = None
            return False

    def _construir(self):
        try:
            def avance(n, _):
                self._leidos = n
            parcial = self.parcial
            entradas, completo = indexar_drive(self.raiz, destino=parcial,
                                               avance=avance, hilos=8)
            self.entradas, self.completo = entradas, completo
            self.fecha = datetime.datetime.now()
            self.error = None
            self._memo = None
            self._guardar_disco()
        except Exception as error:            # el indice anterior sigue
            self.error = str(error)
        finally:
            self._construyendo = False
            self.parcial = []

    def para_buscar(self):
        """(entradas, es_parcial): el indice listo o, la primera vez, lo
        que ya se haya leido."""
        if self.entradas or not self.construyendo:
            return self.entradas, False
        return list(self.parcial), True

    def buscar(self, consulta, empresa, tipos, fecha, orden):
        """buscar_en_indice con memoria de la ultima busqueda: al tocar
        otros controles de la pagina no se vuelve a recorrer el indice."""
        entradas, parcial = self.para_buscar()
        clave = (id(entradas), len(entradas), consulta, empresa,
                 tuple(tipos or []), fecha, orden)
        if not parcial and self._memo and self._memo[0] == clave:
            return self._memo[1], parcial
        resultados = buscar_en_indice(entradas, consulta, empresa, tipos,
                                      fecha, orden)
        if not parcial:
            self._memo = (clave, resultados)
        return resultados, parcial

    def edad_texto(self):
        if not self.fecha:
            return "sin índice todavía"
        minutos = int((datetime.datetime.now() - self.fecha)
                      .total_seconds() // 60)
        if minutos < 1:
            return "actualizado hace menos de un minuto"
        if minutos < 60:
            return f"actualizado hace {minutos} min"
        return f"actualizado el {self.fecha:%d/%m/%Y %H:%M}"


def _rango_fecha(clave, hoy=None):
    """(desde, hasta) en timestamp para el filtro de fecha, o None."""
    valor = FECHAS_FILTRO.get(clave)
    if not valor:
        return None
    hoy = hoy or datetime.datetime.now()
    if isinstance(valor, int):
        return (hoy - datetime.timedelta(days=valor)).timestamp(), None
    anio = hoy.year if valor == "anio" else hoy.year - 1
    return (datetime.datetime(anio, 1, 1).timestamp(),
            datetime.datetime(anio + 1, 1, 1).timestamp())


def buscar_en_indice(entradas, consulta="", empresa=None, tipos=None,
                     fecha="Cualquier fecha", orden="Relevancia"):
    """
    Filtra el indice: nombre (todas las palabras, sin tildes ni
    mayusculas), empresa (carpeta de primer nivel), tipos y fecha de
    modificacion. Devuelve la lista de entradas ordenada.
    """
    palabras = comparable(consulta).split()
    frase = " ".join(palabras)
    tipos = set(tipos or [])
    rango = _rango_fecha(fecha)
    empresa_cmp = comparable(empresa) if empresa else None
    salida = []
    for entrada in entradas:
        (ruta, nombre, nombre_cmp, es_dir, mtime, tam, nivel1, nivel1_cmp,
         tipo) = entrada
        if empresa_cmp and nivel1_cmp != empresa_cmp:
            continue
        if empresa_cmp and es_dir and nombre_cmp == empresa_cmp \
                and not palabras:
            continue                        # la propia carpeta de la empresa
        if palabras and not all(p in nombre_cmp for p in palabras):
            continue
        if tipos and tipo not in tipos:
            continue
        if rango and (mtime < rango[0] or (rango[1] and mtime >= rango[1])):
            continue
        salida.append(entrada)
    if orden == "Más reciente primero":
        salida.sort(key=lambda e: -e[4])
    elif orden == "Nombre (A-Z)":
        salida.sort(key=lambda e: e[1].casefold())
    else:
        salida.sort(key=lambda e: (bool(frase) and not e[2].startswith(frase),
                                   not e[3], e[0].count("\\") + e[0].count("/"),
                                   -e[4]))
    return salida


def fecha_corta(mtime):
    if not mtime:
        return ""
    try:
        return datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y")
    except (OSError, OverflowError, ValueError):
        return ""


def tamano_legible(tam):
    if not tam:
        return ""
    for unidad in ("B", "KB", "MB", "GB"):
        if tam < 1024 or unidad == "GB":
            return f"{tam:,.0f} {unidad}" if unidad == "B" else \
                f"{tam:,.1f} {unidad}"
        tam /= 1024
    return ""


def raiz_que_contiene(ruta, raices):
    """La raiz permitida (la mas especifica) que contiene la ruta."""
    candidatas = [Path(r) for r in raices if r and ruta_dentro_de(ruta, r)]
    return max(candidatas, key=lambda p: len(p.parts)) if candidatas else None


def migas_de(ruta, raices):
    """Segmentos [{n, r}] desde la raiz permitida hasta la ruta."""
    base = None
    for r in raices:                      # se prefiere Mi unidad como base
        if r and ruta_dentro_de(ruta, r):
            base = Path(r)
            break
    if base is None:
        return [{"n": Path(ruta).name or str(ruta), "r": str(ruta)}]
    migas = [{"n": base.name or str(base), "r": str(base)}]
    actual = base
    for parte in Path(ruta).resolve().relative_to(base.resolve()).parts:
        actual = actual / parte
        migas.append({"n": parte, "r": str(actual)})
    return migas


def datos_carpeta_visor(ruta, raices):
    """Datos del explorador para una carpeta."""
    carpetas, archivos, ocultos = listar_carpeta(ruta)

    def plano(x):
        return {"n": x["n"], "r": x["r"], "d": x["d"],
                "f": fecha_corta(x["m"]), "t": tamano_legible(x["t"]),
                "e": extension(x["n"]) if not x["d"] else ""}
    return {"modo": "carpeta", "actual": str(ruta),
            "migas": migas_de(ruta, raices),
            "carpetas": [plano(x) for x in carpetas],
            "archivos": [plano(x) for x in archivos], "ocultos": ocultos}


def datos_resultados_visor(resultados, carpeta_base, consulta="",
                           limite=MAX_RESULTADOS):
    """Resultados agrupados por empresa (carpeta de primer nivel)."""
    grupos = OrderedDict()
    base = Path(carpeta_base)
    for ruta, nombre, _, es_dir, mtime, tam, nivel1, *_ in \
            resultados[:limite]:
        clave = nivel1 or "(en la raíz)"
        if clave not in grupos:
            grupos[clave] = {"n": clave,
                             "r": str(base / nivel1) if nivel1 else str(base),
                             "items": []}
        padre = Path(ruta).parent
        try:
            sub = padre.relative_to(base / nivel1) if nivel1 else \
                padre.relative_to(base)
            sub = " › ".join(sub.parts)
        except ValueError:
            sub = str(padre)
        grupos[clave]["items"].append({
            "n": nombre, "r": ruta, "d": es_dir, "p": str(padre), "s": sub,
            "f": fecha_corta(mtime), "t": tamano_legible(tam),
            "e": extension(nombre) if not es_dir else ""})
    return {"modo": "resultados", "grupos": list(grupos.values()),
            "total": len(resultados), "mostrados": min(len(resultados),
                                                       limite),
            "palabras": comparable(consulta).split()}


def ruta_dentro_de(ruta, raiz):
    try:
        Path(ruta).resolve().relative_to(Path(raiz).resolve())
        return True
    except (ValueError, OSError):
        return False


def abrir_en_sistema(ruta, raices, ubicar=False):
    """
    Abre la carpeta en el Explorador o el archivo con su programa. Con
    ubicar=True abre la carpeta que lo contiene con el archivo
    seleccionado. Solo rutas dentro de las raices permitidas.
    """
    import os
    import subprocess
    if isinstance(raices, (str, Path)):
        raices = [raices]
    if not any(r and ruta_dentro_de(ruta, r) for r in raices):
        raise ValueError("La ruta no está dentro de Mi unidad ni de la "
                         "carpeta de empresas.")
    ruta = os.path.normpath(str(ruta))
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Ya no existe: {ruta}")
    if os.name == "nt":
        if ubicar:
            subprocess.Popen(f'explorer /select,"{ruta}"')
        elif os.path.isdir(ruta):
            subprocess.Popen(["explorer", ruta])
        else:
            os.startfile(ruta)                      # programa asociado
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", ruta] if ubicar else ["open", ruta])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(ruta) if ubicar
                          else ruta])


# Explorador interactivo (componente de Streamlit con su propio HTML). Se
# escribe en una carpeta temporal para que funcione tambien empaquetado.
HTML_EXPLORADOR_DRIVE = r"""<!doctype html>
<html lang="es" translate="no"><head><meta charset="utf-8">
<meta name="google" content="notranslate">
<style>
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: transparent;
  font-family: Inter, "Segoe UI", system-ui, Arial, sans-serif; color: #F4F0F2;
  -webkit-font-smoothing: antialiased; }
button { font-family: inherit; }
.ex-marco { border: 1px solid #39343B; border-radius: 12px; overflow: hidden;
  background: #1F1C20; box-shadow: 0 1px 2px rgba(20,18,20,.05); }
.ex-barra { display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  background: #1F1C20; color: #F4F0F2; padding: 10px 12px;
  border-bottom: 1px solid #39343B; }
.ex-migas { display: flex; flex-wrap: wrap; align-items: center; gap: 2px;
  flex: 1 1 360px; min-width: 0; font-size: 13px; }
.ex-miga { background: transparent; border: 0; color: #C9C1C6; font-weight: 500;
  font-size: 13px; padding: 3px 6px; border-radius: 6px; cursor: pointer;
  max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ex-miga:hover { background: #2A272A; color: #F4F0F2; }
.ex-miga.ultima { color: #F4F0F2; font-weight: 600; cursor: default; background: transparent; }
.ex-sep { color: #8A8287; }
.ex-resumen { font-size: 13px; font-weight: 500; color: #C9C1C6; flex: 1 1 300px; }
.ex-resumen b { color: #F4F0F2; font-weight: 600; }
.ex-btn { border: 1px solid #4A454A; background: #1F1C20; color: #E6E0E3;
  border-radius: 6px; font-weight: 600; font-size: 12px; padding: 5px 10px;
  cursor: pointer; white-space: nowrap; }
.ex-btn:hover { border-color: #8A8287; background: #2A272A; color: #FFFFFF; }
.ex-btn.prim { background: #C20C7B; border-color: #C20C7B; color: #fff; }
.ex-btn.prim:hover { background: #A30A67; border-color: #A30A67; color: #FFFFFF; }
.ex-cuerpo { overflow: auto; padding: 14px; background: #151316; }
.ex-titulo { font-size: 12px; font-weight: 600; color: #A39BA0; margin: 4px 2px 8px; }
.ex-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 8px; margin-bottom: 18px; }
.ex-tile { position: relative; display: flex; align-items: center; gap: 10px;
  background: #1F1C20; border: 1px solid #39343B; border-radius: 10px;
  padding: 10px 40px 10px 10px; cursor: pointer; min-height: 52px;
  transition: border-color .12s, box-shadow .12s; }
.ex-tile:hover { border-color: #E0118F; box-shadow: 0 0 0 3px rgba(224,17,143,.12); }
.ex-tile:focus-visible, .ex-fila:focus-visible { outline: 2px solid #E0118F;
  outline-offset: 2px; }
.ex-tile .ex-nombre { font-weight: 500; font-size: 13px; line-height: 1.3;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; word-break: break-word; }
.ex-tile .ex-abrir { position: absolute; right: 7px; top: 50%;
  transform: translateY(-50%); width: 28px; height: 28px; border-radius: 6px;
  border: 1px solid #39343B; background: #1F1C20; cursor: pointer; font-size: 13px;
  color: #A39BA0; display: flex; align-items: center; justify-content: center; padding: 0; }
.ex-tile .ex-abrir:hover { border-color: #E0118F; color: #FFFFFF; background: rgba(224,17,143,.18); }
.ex-ico { flex: none; width: 34px; height: 24px; border-radius: 5px;
  display: flex; align-items: center; justify-content: center; font-size: 9px;
  font-weight: 700; color: #fff; letter-spacing: .02em; }
.ex-ico svg { width: 24px; height: 24px; }
.ex-tabla { background: #1F1C20; border: 1px solid #39343B; border-radius: 10px;
  overflow: hidden; margin-bottom: 18px; }
.ex-fila { display: grid; grid-template-columns: 34px minmax(0, 1fr) 92px 78px auto;
  align-items: center; gap: 10px; padding: 8px 12px; border-top: 1px solid #2A272A;
  cursor: pointer; font-size: 13px; }
.ex-fila:first-child { border-top: 0; }
.ex-fila:hover { background: #232023; }
.ex-fila .ex-nombre { min-width: 0; }
.ex-fila .ex-n1 { font-weight: 500; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.ex-fila .ex-sub { font-size: 11.5px; color: #A39BA0; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; margin-top: 1px; }
.ex-dato { font-size: 12px; color: #A39BA0; text-align: right;
  font-variant-numeric: tabular-nums; white-space: nowrap; }
.ex-acc { display: flex; gap: 5px; justify-content: flex-end; }
.ex-acc .ex-btn { padding: 3px 8px; font-size: 11px; }
mark { background: rgba(224,17,143,.32); color: #FFD1EC; border-radius: 3px; padding: 0 1px;
  font-weight: 600; }
.ex-grupo { margin-bottom: 16px; }
.ex-grupo-cab { display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  background: #1F1C20; color: #F4F0F2; border: 1px solid #39343B; border-bottom: 0;
  border-radius: 10px 10px 0 0; padding: 9px 12px; }
.ex-grupo-cab .ex-gnom { font-weight: 600; font-size: 13.5px; flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ex-cuenta { background: #2A272A; color: #C9C1C6; border-radius: 999px;
  font-size: 11px; font-weight: 600; padding: 2px 8px;
  font-variant-numeric: tabular-nums; }
.ex-grupo .ex-tabla { border-radius: 0 0 10px 10px; }
.ex-vacio { padding: 22px; text-align: center; color: #A39BA0; font-size: 13px; }
.ex-nota { font-size: 12px; color: #A39BA0; margin: -8px 2px 12px; }
@media (max-width: 720px) {
  .ex-fila { grid-template-columns: 34px minmax(0, 1fr) auto; }
  .ex-fila .ex-dato { display: none; }
}
</style></head>
<body>
<div class="ex-marco">
  <div class="ex-barra" id="barra"></div>
  <div class="ex-cuerpo" id="cuerpo"></div>
</div>
<script>
(function () {
  var COLORES = { xls: "#1D6F42", xlsx: "#1D6F42", xlsm: "#1D6F42", xlsb: "#1D6F42",
    csv: "#1D6F42", ods: "#1D6F42", gsheet: "#1D6F42", pdf: "#C00000",
    doc: "#2B579A", docx: "#2B579A", gdoc: "#2B579A", odt: "#2B579A",
    ppt: "#C43E1C", pptx: "#C43E1C", gslides: "#C43E1C", txt: "#595959",
    xml: "#A30A67", json: "#A30A67", zip: "#7F6000", rar: "#7F6000", "7z": "#7F6000",
    png: "#6B3FA0", jpg: "#6B3FA0", jpeg: "#6B3FA0", gif: "#6B3FA0", heic: "#6B3FA0" };
  var CARPETA = '<svg viewBox="0 0 24 24"><path fill="#6B6568" d="M2.5 6A1.5 1.5 0 0 1 4 4.5h5.2l2 2H20A1.5 1.5 0 0 1 21.5 8v10A1.5 1.5 0 0 1 20 19.5H4A1.5 1.5 0 0 1 2.5 18z"/><path fill="#E0118F" d="M2.5 9h19v1.8h-19z"/></svg>';
  var palabras = [];

  function enviar(tipo, datos) {
    var m = { isStreamlitMessage: true, type: tipo };
    for (var k in (datos || {})) { m[k] = datos[k]; }
    window.parent.postMessage(m, "*");
  }
  function accion(a, ruta) {
    enviar("streamlit:setComponentValue",
           { value: { accion: a, ruta: ruta, t: Date.now() }, dataType: "json" });
  }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function sinTildes(t) {
    return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
  }
  // Resalta las palabras buscadas sin importar tildes ni mayusculas.
  function resaltar(nombre) {
    if (!palabras.length) { return esc(nombre); }
    var base = sinTildes(nombre), marcas = new Array(nombre.length).fill(false);
    palabras.forEach(function (p) {
      var i = base.indexOf(p);
      while (p && i >= 0) {
        for (var k = i; k < i + p.length && k < marcas.length; k++) { marcas[k] = true; }
        i = base.indexOf(p, i + p.length);
      }
    });
    var salida = "", abierto = false;
    for (var i = 0; i < nombre.length; i++) {
      if (marcas[i] && !abierto) { salida += "<mark>"; abierto = true; }
      if (!marcas[i] && abierto) { salida += "</mark>"; abierto = false; }
      salida += esc(nombre[i]);
    }
    return salida + (abierto ? "</mark>" : "");
  }
  function icono(item) {
    if (item.d) { return '<span class="ex-ico">' + CARPETA + '</span>'; }
    var ext = item.e || "";
    return '<span class="ex-ico" style="background:' + (COLORES[ext] || "#4A454A") +
      '">' + esc((ext || "ARCH").slice(0, 4).toUpperCase()) + '</span>';
  }
  function fila(item, conRuta) {
    var botones = '<span class="ex-acc">';
    if (conRuta) {
      botones += '<button class="ex-btn" data-a="ubicar" title="Abrir la carpeta que lo contiene, con el elemento seleccionado">Ubicar</button>' +
        '<button class="ex-btn" data-a="ver" title="Ver la carpeta que lo contiene aquí">Ver carpeta</button>';
    }
    botones += '</span>';
    return '<div class="ex-fila" tabindex="0" data-r="' + esc(item.r) + '" data-p="' +
      esc(item.p || "") + '" data-d="' + (item.d ? 1 : 0) + '" title="' + esc(item.r) + '">' +
      icono(item) + '<div class="ex-nombre"><div class="ex-n1">' + resaltar(item.n) +
      '</div>' + (conRuta && item.s ? '<div class="ex-sub">' + esc(item.s) + '</div>' : "") +
      '</div><span class="ex-dato">' + esc(item.f) + '</span><span class="ex-dato">' +
      esc(item.t) + '</span>' + botones + '</div>';
  }

  function dibujarCarpeta(a) {
    var barra = '<div class="ex-migas">';
    (a.migas || []).forEach(function (m, i) {
      var ultima = i === a.migas.length - 1;
      barra += (i ? '<span class="ex-sep">›</span>' : "") +
        '<button class="ex-miga' + (ultima ? " ultima" : "") + '" data-r="' + esc(m.r) +
        '" title="' + esc(m.r) + '">' + esc(m.n) + '</button>';
    });
    barra += '</div><button class="ex-btn prim" id="abrirActual">Abrir en el Explorador</button>';
    document.getElementById("barra").innerHTML = barra;
    var html = "";
    if (a.carpetas.length) {
      html += '<div class="ex-titulo">Carpetas · ' + a.carpetas.length + '</div><div class="ex-grid">';
      a.carpetas.forEach(function (c) {
        html += '<div class="ex-tile" tabindex="0" data-r="' + esc(c.r) + '" title="' +
          esc(c.r) + '">' + icono(c) + '<span class="ex-nombre">' + esc(c.n) +
          '</span><button class="ex-abrir" title="Abrir en el Explorador de Windows">↗</button></div>';
      });
      html += '</div>';
    }
    if (a.archivos.length) {
      html += '<div class="ex-titulo">Archivos · ' + a.archivos.length + '</div><div class="ex-tabla">';
      a.archivos.forEach(function (f) { html += fila(f, false); });
      html += '</div>';
    }
    if (a.ocultos) {
      html += '<div class="ex-nota">… y ' + a.ocultos + ' elementos más en esta carpeta. Usa la búsqueda o ábrela en el Explorador.</div>';
    }
    if (!a.carpetas.length && !a.archivos.length) {
      html = '<div class="ex-vacio">Esta carpeta está vacía.</div>';
    }
    document.getElementById("cuerpo").innerHTML = html;
    var abrirActual = document.getElementById("abrirActual");
    abrirActual.onclick = function () { accion("abrir", a.actual); };
  }

  function dibujarResultados(a) {
    var texto = '<b>' + a.total + '</b> resultado' + (a.total === 1 ? "" : "s");
    if (a.grupos.length > 1) { texto += ' en <b>' + a.grupos.length + '</b> carpetas'; }
    if (a.mostrados < a.total) { texto += ' · se muestran los primeros ' + a.mostrados; }
    document.getElementById("barra").innerHTML = '<div class="ex-resumen">' + texto + '</div>';
    var html = "";
    a.grupos.forEach(function (g) {
      html += '<div class="ex-grupo"><div class="ex-grupo-cab"><span class="ex-gnom" title="' +
        esc(g.r) + '">' + esc(g.n) + '</span><span class="ex-cuenta">' + g.items.length +
        '</span><button class="ex-btn" data-ver="' + esc(g.r) + '">Ver carpeta ›</button></div><div class="ex-tabla">';
      g.items.forEach(function (it) { html += fila(it, true); });
      html += '</div></div>';
    });
    if (!a.grupos.length) { html = '<div class="ex-vacio">Sin resultados con estos filtros.</div>'; }
    document.getElementById("cuerpo").innerHTML = html;
  }

  function enlazar() {
    document.querySelectorAll(".ex-miga").forEach(function (b) {
      if (!b.classList.contains("ultima")) {
        b.onclick = function () { accion("navegar", b.getAttribute("data-r")); };
      }
    });
    document.querySelectorAll(".ex-tile").forEach(function (t) {
      var r = t.getAttribute("data-r");
      t.onclick = function (e) {
        if (e.target.closest(".ex-abrir")) { accion("abrir", r); }
        else { accion("navegar", r); }
      };
      t.onkeydown = function (e) { if (e.key === "Enter") { accion("navegar", r); } };
    });
    document.querySelectorAll(".ex-fila").forEach(function (f) {
      var r = f.getAttribute("data-r"), p = f.getAttribute("data-p");
      f.onclick = function (e) {
        var b = e.target.closest("button");
        if (b && b.getAttribute("data-a") === "ubicar") { accion("ubicar", r); return; }
        if (b && b.getAttribute("data-a") === "ver") { accion("navegar", p); return; }
        accion("abrir", r);
      };
      f.onkeydown = function (e) { if (e.key === "Enter") { accion("abrir", r); } };
    });
    document.querySelectorAll("[data-ver]").forEach(function (b) {
      b.onclick = function () { accion("navegar", b.getAttribute("data-ver")); };
    });
  }

  function dibujar(args) {
    var datos = args.datos || {};
    palabras = (datos.palabras || []).filter(function (p) { return p; });
    var cuerpo = document.getElementById("cuerpo");
    cuerpo.style.maxHeight = (args.alto || 620) + "px";
    if (datos.modo === "resultados") { dibujarResultados(datos); }
    else if (datos.modo === "carpeta") { dibujarCarpeta(datos); }
    else { cuerpo.innerHTML = '<div class="ex-vacio">Sin datos.</div>'; }
    enlazar();
    cuerpo.scrollTop = 0;
    enviar("streamlit:setFrameHeight", { height: document.body.scrollHeight + 8 });
  }

  window.addEventListener("message", function (e) {
    if (e.data && e.data.type === "streamlit:render") { dibujar(e.data.args || {}); }
  });
  window.gmyaDibujar = dibujar;                 // para pruebas
  enviar("streamlit:componentReady", { apiVersion: 1 });
})();
</script>
</body></html>
"""


def carpeta_componente_explorador():
    import tempfile
    carpeta = Path(tempfile.gettempdir()) / "gmya_componentes" / \
        "explorador_drive"
    carpeta.mkdir(parents=True, exist_ok=True)
    indice = carpeta / "index.html"
    try:
        actual = indice.read_text(encoding="utf-8")
    except OSError:
        actual = ""
    if actual != HTML_EXPLORADOR_DRIVE:
        indice.write_text(HTML_EXPLORADOR_DRIVE, encoding="utf-8")
    return carpeta
