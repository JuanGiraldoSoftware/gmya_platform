"""
Pruebas de regresion con documentos reales (v6.14).

    python -m pruebas.regresion  CARPETA_DE_DATOS

Cada caso busca sus archivos en una subcarpeta de CARPETA_DE_DATOS; si no
estan, el caso se SALTA (los documentos de clientes no viajan con el
proyecto: se guardan en un equipo de la firma). Para cada caso se
comprueba:
  1. El resultado esperado (diferencias, conteos, totales leidos), con
     tolerancia 0: el valor debe ser exacto al centavo.
  2. El panel de diferencias: su composicion suma EXACTO total A - total B
     (no aparece "Sin explicar") y lo pendiente coincide con la diferencia
     de la conciliacion.
  3. Los Excel generados: se recalculan con LibreOffice (si esta
     instalado) y no deben tener celdas con error (#REF!, #VALUE!...);
     en DIAN, la hoja RESUMEN debe dar las mismas diferencias del analisis.
Sale con codigo 1 si algo falla.

Los casos (archivos, resultados esperados y comprobaciones) usan datos
reales de clientes, asi que NO estan en el repositorio: viven en
CARPETA_DE_DATOS/casos_privados.py (lista CASOS = [(nombre, funcion)]).
Este archivo solo tiene el motor, las ayudas y pruebas sin documentos.
"""
import copy
from collections import Counter
import datetime
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types
import warnings
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

warnings.simplefilter("ignore")
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:                                    # la logica no necesita la interfaz
    import streamlit  # noqa: F401
except ImportError:
    _st = types.ModuleType("streamlit")
    _m = MagicMock()

    def _attr(n):
        if n.startswith("cache"):
            raise AttributeError(n)
        return getattr(_m, n)
    _st.__getattr__ = _attr
    sys.modules["streamlit"] = _st
    for _n in ("streamlit.runtime", "streamlit.components",
               "streamlit.components.v1"):
        sys.modules[_n] = MagicMock()

ERRORES_EXCEL = ("#REF!", "#VALUE!", "#DIV/0!", "#NAME?", "#N/A", "#NUM!",
                 "Err:")

fallas, resumen = [], []


def _ok(caso, condicion, texto):
    if not condicion:
        fallas.append(f"{caso}: {texto}")
    return condicion


def _igual(a, b):
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.005


def _leer(carpeta, *nombres):
    rutas = [carpeta / n for n in nombres]
    if not all(r.is_file() for r in rutas):
        return None
    return [r.read_bytes() for r in rutas]


# ------------------------------------------------------------
# Excel: recalculo con LibreOffice y celdas con error
# ------------------------------------------------------------
def _soffice():
    for nombre in ("soffice", "libreoffice"):
        if shutil.which(nombre):
            return shutil.which(nombre)
    for ruta in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                 r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.isfile(ruta):
            return ruta
    return None


def excel_recalculado(contenido):
    """Libro de openpyxl (data_only) con las formulas recalculadas, o None
    si LibreOffice no esta instalado."""
    from openpyxl import load_workbook
    programa = _soffice()
    if not programa:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        origen = Path(tmp) / "libro.xlsx"
        origen.write_bytes(contenido)
        salida = Path(tmp) / "rc"
        subprocess.run([programa, "--headless", "--calc", "--convert-to",
                        "xlsx", "--outdir", str(salida), str(origen)],
                       capture_output=True, timeout=240)
        archivo = salida / "libro.xlsx"
        if not archivo.is_file():
            return None
        return load_workbook(io.BytesIO(archivo.read_bytes()),
                             data_only=True)


def revisar_excel(caso, contenido, etiqueta):
    libro = excel_recalculado(contenido)
    if libro is None:
        resumen.append(f"  {caso}: {etiqueta} sin recalcular (no hay "
                       "LibreOffice)")
        return None
    malas = [f"{h.title}!{c.coordinate}" for h in libro for fila in
             h.iter_rows() for c in fila if isinstance(c.value, str)
             and c.value.startswith(ERRORES_EXCEL)]
    _ok(caso, not malas, f"{etiqueta}: celdas con error {malas[:5]}")
    return libro


# ------------------------------------------------------------
# Panel de diferencias: identidad
# ------------------------------------------------------------
def revisar_panel(caso, conceptos):
    from gmya.ui.visual import (completar_composicion, html_composicion,
                                html_partidas, html_panel_resumen)
    for c in conceptos:
        n = len(c["composicion"])
        completar_composicion(c)
        if len(c["composicion"]) != n:
            _ok(caso, False, f"panel {c['clave']}: la composicion no suma "
                f"A - B ({c['composicion'][-1]['valor']} sin explicar)")
        html = (html_panel_resumen(c["clave"], c.get("sub", ""), c["dona"],
                                   c["centro"], c["centro_sub"],
                                   datos=c.get("datos") or ())
                + html_composicion(c) + html_partidas(c["partidas"]))
        _ok(caso, "None" not in html and "nan" not in html.lower().split(),
            f"panel {c['clave']}: texto 'None' en el HTML")


def pruebas_estadistica():
    """Sin documentos: porcentajes que suman 100 y tramos de vencimiento."""
    from gmya.comun.estadistica import (antiguedad, porcentajes,
                                        texto_porcentaje)
    pcs = porcentajes([907, 60, 4, 0])
    _ok("estadistica", abs(sum(pcs) - 100) < 1e-9 and pcs[2] > 0,
        f"porcentajes {pcs}")
    _ok("estadistica", texto_porcentaje(0.0, 3) == "<0,1 %",
        "un valor distinto de cero no puede mostrarse como 0 %")
    hoy = datetime.date(2026, 11, 20)
    docs = [(hoy, 1), (hoy - datetime.timedelta(days=1), 2),
            (hoy - datetime.timedelta(days=30), 4),
            (hoy - datetime.timedelta(days=31), 8),
            (hoy - datetime.timedelta(days=181), 16), (None, 32)]
    t = {x["tramo"]: x["valor"] for x in antiguedad(
        docs, hoy, lambda d: d[1], lambda d: d[0])}
    _ok("estadistica", t == {"al_dia": 1, "d30": 6, "d60": 8, "d90": 0,
                             "d180": 0, "mas": 16, "sin": 32},
        f"tramos de antiguedad {t}")
    print("  OK       estadistica: porcentajes y tramos" if not any(
        f.startswith("estadistica") for f in fallas) else
        "  FALLA    estadistica")


def pruebas_uso():
    """Sin documentos: periodo de un dia, tramos de 10 minutos y pico."""
    from gmya.registro.logica import (acciones_por_hora, filtrar_periodo,
                                      tramos_del_dia)
    def f(fecha, hora, ev, it="0", p="ANA"):
        return {"fecha": fecha, "hora": hora, "persona": p, "evento": ev,
                "interacciones": it, "modulo": "dian", "detalle": ""}
    filas = [f("2026-11-23", "09:10:00", "abierta", "2"),
             f("2026-11-23", "09:20:00", "abierta", "0"),
             f("2026-11-23", "09:25:00", "clic"),
             f("2026-11-24", "10:00:00", "abierta", "1")]
    d = datetime.date(2026, 11, 23)
    dia = filtrar_periodo(filas, d, d)
    t = tramos_del_dia(dia)["ANA"]
    _ok("uso", len(dia) == 3 and t == [(540, 550, "uso"), (550, 560,
                                                          "abierta"),
                                       (560, 570, "uso")],
        f"tramos del dia {t}")
    _ok("uso", acciones_por_hora(dia)[9] == 1, "acciones por hora")
    print("  OK       uso: un dia y tramos de 10 minutos" if not any(
        x.startswith("uso") for x in fallas) else "  FALLA    uso")


AYUDAS = ("_ok", "_igual", "_leer", "excel_recalculado", "revisar_excel",
          "revisar_panel", "fallas", "resumen", "Decimal", "Counter", "copy",
          "datetime", "io", "Path", "ERRORES_EXCEL", "tempfile", "os",
          "shutil", "subprocess", "sys")


def casos_privados(base):
    """CASOS de base/casos_privados.py (datos de clientes, fuera del repo)."""
    import importlib.util
    ruta = Path(base) / "casos_privados.py"
    if not ruta.is_file():
        print(f"  (sin {ruta}: solo pruebas sin documentos)")
        return []
    spec = importlib.util.spec_from_file_location("casos_privados", ruta)
    modulo = importlib.util.module_from_spec(spec)
    modulo.__dict__.update({n: globals()[n] for n in AYUDAS})
    spec.loader.exec_module(modulo)
    return list(getattr(modulo, "CASOS", []))


def main(carpeta):
    base = Path(carpeta)
    corridos = 0
    pruebas_estadistica()
    pruebas_uso()
    for nombre, funcion in casos_privados(base):
        antes = len(fallas)
        try:
            texto = funcion(base / nombre)
        except Exception as e:          # un caso roto no detiene los demas
            import traceback
            fallas.append(f"{nombre}: error {type(e).__name__}: {e}")
            traceback.print_exc()
            texto = "ERROR"
        if texto is None:
            print(f"  SALTADO  {nombre} (faltan los archivos)")
            continue
        corridos += 1
        estado = "OK" if len(fallas) == antes else "FALLA"
        print(f"  {estado:8} {nombre}: {texto}")
    for r in resumen:
        print(r)
    for f in fallas:
        print("  ERROR", f)
    print(f"Regresion {'OK' if not fallas else 'FALLIDA'}: {corridos} "
          f"caso(s) corridos, {len(fallas)} error(es).")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.environ.get("GMYA_DATOS", "pruebas/datos")))
