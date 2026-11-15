"""Configuracion local del equipo en ~/.gmya/config.json (persona asignada,
rutas de Drive, id del equipo).

Contrato:
  leer_config() -> dict (vacio si no existe o esta danado).
  guardar_config(**claves) -> actualiza solo las claves indicadas;
      True si se pudo escribir.

Depende de: (solo biblioteca estandar / terceros)
"""

from pathlib import Path


ARCHIVO_CONFIG = Path.home() / ".gmya" / "config.json"


def leer_config():
    import json
    try:
        return json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_config(**valores):
    import json
    datos = leer_config()
    datos.update(valores)
    try:
        ARCHIVO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        ARCHIVO_CONFIG.write_text(json.dumps(datos, ensure_ascii=False,
                                             indent=2), encoding="utf-8")
        return True
    except Exception:
        return False
