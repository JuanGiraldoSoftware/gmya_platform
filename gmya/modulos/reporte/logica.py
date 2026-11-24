"""Reporte de errores de la plataforma (sin Streamlit).

Contrato:
  carpeta_reportes(carpeta_gmya) -> Path de la carpeta de reportes dentro de
      SISTEMAS del Drive (junto a "GMYA Tools"), o None si no se encuentra.
  guardar_reporte(carpeta_gmya, datos, usados, generados, momento=None)
      -> (Path de la carpeta del reporte, True si quedo en el Drive).
      datos: {"persona", "modulo", "descripcion", "version", "equipo",
              "nombre_equipo", "errores"}; usados/generados: [(nombre, bytes)].
      Si el Drive no esta disponible se guarda en ~/.gmya/reportes_pendientes
      y se sube la proxima vez (subir_pendientes).
REGLAS:
  - Nunca se escribe en 001. EMPRESAS ACTIVAS USO DIARIO.
  - El reporte SI lleva los archivos que la persona adjunta (para poder
    reproducir el error); por eso la carpeta debe compartirse solo con
    sistemas / administradores.

Depende de: gmya.comun.texto, gmya.registro.logica
"""

import datetime
import re
import shutil
from pathlib import Path

from gmya.comun.texto import comparable
from gmya.registro.logica import _es_carpeta_de_empresas

CARPETA_REPORTES = "REPORTES DE ERRORES GMYA TOOLS"
PENDIENTES_REPORTES = Path.home() / ".gmya" / "reportes_pendientes"
SUB_USADOS = "1 ARCHIVOS USADOS"
SUB_GENERADOS = "2 ARCHIVO GENERADO POR LA PLATAFORMA"


def _sistemas(carpeta_gmya):
    """Carpeta SISTEMAS que contiene a "GMYA Tools" (o su carpeta padre si
    no se llama asi)."""
    if not carpeta_gmya:
        return None
    ruta = Path(carpeta_gmya)
    for padre in [ruta] + list(ruta.parents):
        if comparable(padre.name) == "SISTEMAS":
            return padre
    return ruta.parent


def carpeta_reportes(carpeta_gmya):
    base = _sistemas(carpeta_gmya)
    if base is None or _es_carpeta_de_empresas(base):
        return None
    return base / CARPETA_REPORTES


def _limpio(texto, largo=60):
    texto = re.sub(r'[<>:"/\\|?*\r\n\t]+', " ", str(texto or "")).strip()
    return re.sub(r"\s+", " ", texto)[:largo].strip(" .") or "SIN NOMBRE"


def _escribir(destino, datos, usados, generados, momento):
    destino.mkdir(parents=True, exist_ok=False)
    lineas = [
        "REPORTE DE ERROR · GMYA TOOLS",
        f"Fecha: {momento:%Y-%m-%d %H:%M:%S}",
        f"Persona: {datos.get('persona') or ''}",
        f"Equipo: {datos.get('equipo') or ''} "
        f"({datos.get('nombre_equipo') or ''})",
        f"Versión: {datos.get('version') or ''}",
        f"Módulo: {datos.get('modulo') or ''}",
        "",
        "DESCRIPCIÓN DEL ERROR:",
        str(datos.get("descripcion") or "").strip(),
        "",
        f"{SUB_USADOS}: " + (", ".join(n for n, _ in usados) or "(ninguno)"),
        f"{SUB_GENERADOS}: " + (", ".join(n for n, _ in generados)
                                or "(ninguno)"),
    ]
    if datos.get("errores"):
        lineas += ["", "ÚLTIMOS ERRORES REGISTRADOS EN ESTA SESIÓN:"]
        lineas += [f"- {e}" for e in datos["errores"]]
    (destino / "REPORTE.txt").write_text("\n".join(lineas) + "\n",
                                         encoding="utf-8-sig")
    for sub, archivos in ((SUB_USADOS, usados), (SUB_GENERADOS, generados)):
        if not archivos:
            continue
        carpeta = destino / sub
        carpeta.mkdir(exist_ok=True)
        usados_nombres = set()
        for nombre, contenido in archivos:
            nombre = _limpio(Path(nombre).name, 150)
            base, punto, ext = nombre.rpartition(".")
            n = 2
            while nombre.lower() in usados_nombres:
                nombre = f"{base or ext} ({n}){punto}{ext if base else ''}"
                n += 1
            usados_nombres.add(nombre.lower())
            (carpeta / nombre).write_bytes(bytes(contenido))


def guardar_reporte(carpeta_gmya, datos, usados, generados, momento=None):
    momento = momento or datetime.datetime.now()
    nombre = _limpio(f"{momento:%Y-%m-%d %H%M%S} {datos.get('persona')} "
                     f"{datos.get('modulo')}", 90)
    destino_drive = carpeta_reportes(carpeta_gmya)
    if destino_drive is not None:
        try:
            subir_pendientes(carpeta_gmya)
            final, n = destino_drive / nombre, 2
            while final.exists():
                final = destino_drive / f"{nombre} ({n})"
                n += 1
            _escribir(final, datos, usados, generados, momento)
            return final, True
        except Exception:
            pass
    local, n = PENDIENTES_REPORTES / nombre, 2
    while local.exists():
        local = PENDIENTES_REPORTES / f"{nombre} ({n})"
        n += 1
    _escribir(local, datos, usados, generados, momento)
    return local, False


def subir_pendientes(carpeta_gmya):
    """Copia al Drive los reportes que quedaron en el equipo sin conexion.
    Devuelve cuantos se subieron."""
    destino = carpeta_reportes(carpeta_gmya)
    if destino is None or not PENDIENTES_REPORTES.is_dir():
        return 0
    subidos = 0
    for carpeta in sorted(p for p in PENDIENTES_REPORTES.iterdir()
                          if p.is_dir()):
        try:
            final, n = destino / carpeta.name, 2
            while final.exists():           # nunca se pisa otro reporte
                final = destino / f"{carpeta.name} ({n})"
                n += 1
            shutil.copytree(carpeta, final)
            shutil.rmtree(carpeta, ignore_errors=True)
            subidos += 1
        except Exception:
            continue
    return subidos
