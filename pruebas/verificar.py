"""
Verificacion rapida del proyecto (la corre compilar_firmar_empaquetar.ps1
antes de compilar; tambien: python -m pruebas.verificar).

Comprueba, sin abrir la interfaz ni usar datos de clientes:
  1. Todos los .py compilan (sin errores de sintaxis).
  2. Ningun modulo usa un nombre que no este definido o importado.
  3. Las capas se respetan: un modulo solo importa de capas anteriores
     (evita importaciones circulares).
  4. Todos los modulos de gmya/ y app.py se importan/ejecutan con un
     Streamlit simulado, y cada pantalla del menu existe.
Sale con codigo 1 si algo falla.
"""
import ast
import builtins
import importlib
import runpy
import symtable
import sys
from pathlib import Path
from unittest.mock import MagicMock

RAIZ = Path(__file__).resolve().parent.parent

# Orden de capas: un modulo puede importar solo de prefijos que aparezcan
# ANTES que el suyo en esta lista.
CAPAS = [
    "gmya.config", "gmya.comun", "gmya.ui.componentes", "gmya.ui.estilos",
    "gmya.ui.globos", "gmya.ui.visor", "gmya.modulos.busqueda.logica",
    "gmya.registro.logica", "gmya.modulos.planillas.logica",
    "gmya.modulos.dian.", "gmya.modulos.bancos.", "gmya.modulos.pagos.",
    "gmya.modulos.odoo.logica", "gmya.modulos.nomina.logica",
    "gmya.modulos.nomina.hibrids", "gmya.modulos.nomina.conciliacion",
    "gmya.modulos.reporte.logica",
    "gmya.ui.interfaz_comun",
    "gmya.registro.interfaz", "INTERFACES", "gmya.modulos.inicio", "app",
]


def capa(mod):
    if mod.endswith(".interfaz") and mod.startswith("gmya.modulos."):
        return CAPAS.index("INTERFACES"), mod
    mejor = None
    for i, pref in enumerate(CAPAS):
        if mod == pref or mod.startswith(pref.rstrip(".") + "."):
            mejor = i
    return mejor, mod


def archivos():
    yield RAIZ / "app.py"
    yield from sorted((RAIZ / "gmya").rglob("*.py"))


def nombre_modulo(py):
    partes = py.relative_to(RAIZ).with_suffix("").parts
    return ".".join(p for p in partes if p != "__init__")


def definidos(arbol):
    salida = set()
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            salida.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                salida.add((a.asname or a.name).split(".")[0])
        for x in ast.walk(n) if not isinstance(
                n, (ast.FunctionDef, ast.ClassDef)) else ():
            if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                salida.add(x.id)
    return salida


def revisar_estatico():
    errores = []
    for py in archivos():
        mod = nombre_modulo(py)
        src = py.read_text(encoding="utf-8")
        try:
            arbol = ast.parse(src, str(py))
        except SyntaxError as e:
            errores.append(f"{mod}: error de sintaxis {e}")
            continue
        conocidos = definidos(arbol)
        faltan = set()

        def rec(tabla, nivel):
            for s in tabla.get_symbols():
                if not s.is_referenced():
                    continue
                if nivel == 0 and s.is_assigned():
                    continue
                if nivel == 0 or s.is_global():
                    nm = s.get_name()
                    if nm not in conocidos and not hasattr(builtins, nm) \
                            and nm not in ("__file__", "__name__"):
                        faltan.add(nm)
            for h in tabla.get_children():
                rec(h, nivel + 1)
        rec(symtable.symtable(src, str(py), "exec"), 0)
        if faltan:
            errores.append(f"{mod}: nombres sin definir {sorted(faltan)}")
        c_mod = capa(mod)
        for n in arbol.body:
            if isinstance(n, ast.ImportFrom) and n.module and \
                    n.module.startswith("gmya."):
                c_dep = capa(n.module)
                if c_dep[0] is None or c_mod[0] is None or \
                        c_dep[0] > c_mod[0] or (
                        c_dep[0] == c_mod[0] and
                        CAPAS[c_mod[0]] == "INTERFACES"):
                    errores.append(f"{mod} importa de {n.module}: rompe el "
                                   "orden de capas")
    return errores


def revisar_importacion():
    errores = []
    # Carpeta personal temporal: la verificacion no toca ~/.gmya ni el Drive.
    import os
    import tempfile
    temporal = tempfile.mkdtemp(prefix="gmya_verificacion_")
    os.environ["HOME"] = os.environ["USERPROFILE"] = temporal
    st = MagicMock()
    st.cache_data = None
    st.cache_resource = None
    st.session_state = {}
    st.columns.side_effect = lambda n, **k: [
        MagicMock() for _ in range(n if isinstance(n, int) else len(n))]
    st.button.return_value = False
    for nombre in ("streamlit", "streamlit.runtime", "streamlit.components",
                   "streamlit.components.v1"):
        sys.modules[nombre] = st if nombre == "streamlit" else MagicMock()
    sys.path.insert(0, str(RAIZ))
    for py in archivos():
        if py.name == "app.py":
            continue
        try:
            importlib.import_module(nombre_modulo(py))
        except Exception as e:
            errores.append(f"{nombre_modulo(py)}: no importa ({e!r})")
    try:
        # Sin usuario ni registro de uso: nada se escribe en el Drive.
        registro = importlib.import_module("gmya.registro.interfaz")
        registro._estado_registro = lambda: (None, None)
        ns = runpy.run_path(str(RAIZ / "app.py"), run_name="verificacion")
        inicio = importlib.import_module("gmya.modulos.inicio")
        for clave in inicio.MODULOS:
            if clave not in ns["PANTALLAS"]:
                errores.append(f"app.py: el modulo '{clave}' del menu no "
                               "tiene pantalla en PANTALLAS")
    except Exception as e:
        errores.append(f"app.py: no se ejecuta ({e!r})")
    return errores


def main():
    errores = revisar_estatico() + revisar_importacion()
    for e in errores:
        print("  ERROR", e)
    from gmya.config import VERSION
    if errores:
        print(f"Verificacion FALLIDA ({len(errores)} errores).")
        return 1
    n = sum(1 for _ in archivos())
    print(f"Verificacion OK: {n} archivos, GMYA Tools {VERSION}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
