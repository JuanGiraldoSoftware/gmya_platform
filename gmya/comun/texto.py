"""Normalizacion de texto (sin Streamlit).

Contrato:
  comparable(t)    -> MAYUSCULAS, sin tildes y espacios simples; base de
                      todas las comparaciones de nombres/conceptos.
  decodificar(b)   -> str desde bytes probando utf-8-sig, cp1252, latin-1.
  alfanumerico(t), solo_nit(t), _solo_digitos(t) -> versiones limpias para
                      comparar NIT, numeros de documento, etc.

Depende de: (solo biblioteca estandar / terceros)
"""

import re
import unicodedata


def decodificar(contenido):
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue

    raise ValueError("No se pudo interpretar la codificacion del TXT.")


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def _sin_tildes(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def comparable(texto):
    return re.sub(r"\s+", " ", _sin_tildes(texto)).strip().upper()


def alfanumerico(texto):
    return re.sub(r"[^A-Z0-9]", "", comparable(texto))


def solo_nit(texto):
    """'  900123456-1' -> '900123456'; 800123456 -> '800123456'."""
    texto = str(texto or "").strip()
    if isinstance(texto, float) or re.fullmatch(r"\d+\.0", texto):
        texto = texto.split(".")[0]
    texto = texto.split("-")[0]
    return re.sub(r"\D", "", texto)


def _solo_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))
