"""
Lanzador de GMYA Tools (es el punto de entrada del .exe).

Contrato:
  - Arranca Streamlit con app.py en http://127.0.0.1:<GMYA_PORT> (8502 por
    defecto), sin vigilar archivos y en modo no desarrollo.
  - Abre el navegador cuando el servidor responde, salvo GMYA_NO_BROWSER=1.
  - En el .exe (PyInstaller) app.py viaja como dato junto al ejecutable
    (carpeta _MEIPASS) y el paquete gmya/ va compilado dentro del .exe.
  - Si algo falla, muestra el error y espera Enter (la consola no se cierra
    sola, para poder leerlo).

Uso en desarrollo:  python run_gmyatools.py
"""
import os
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from urllib.request import urlopen

from streamlit.web import cli as stcli

PUERTO = int(os.environ.get("GMYA_PORT", "8502"))
URL = f"http://127.0.0.1:{PUERTO}"
APLICACION = "app.py"


def ruta_recurso(nombre):
    """Archivo junto al programa: _MEIPASS en el .exe, la carpeta de este
    archivo en desarrollo."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent
    return base / nombre


def abrir_navegador():
    for _ in range(60):
        try:
            with urlopen(URL, timeout=1):
                webbrowser.open(URL)
                return
        except Exception:
            time.sleep(1)


def _modulos_para_empaquetar():
    """
    Nunca se ejecuta. Solo existe para que PyInstaller vea estos imports
    (app.py viaja como dato y PyInstaller no lo analiza). Ademas el script
    de compilacion usa --collect-submodules gmya.
    """
    import app  # noqa: F401
    import gmya.modulos.inicio  # noqa: F401
    import difflib, xlrd, pandas, openpyxl, pdfplumber, pypdfium2  # noqa
    import PIL.Image  # noqa: F401


def main():
    aplicacion = ruta_recurso(APLICACION)
    if not aplicacion.exists():
        raise FileNotFoundError(f"No se encontró {APLICACION} en: {aplicacion}")
    # En desarrollo, que app.py encuentre el paquete gmya/ de esta carpeta.
    carpeta = str(aplicacion.parent)
    if carpeta not in sys.path:
        sys.path.insert(0, carpeta)
    if not os.environ.get("GMYA_NO_BROWSER"):
        threading.Thread(target=abrir_navegador, daemon=True).start()
    sys.argv = [
        "streamlit", "run", str(aplicacion),
        "--server.address=127.0.0.1",
        f"--server.port={PUERTO}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\nPresiona Enter para cerrar...")
