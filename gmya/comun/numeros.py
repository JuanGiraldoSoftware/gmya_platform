"""Numeros y dinero (sin Streamlit).

Contrato:
  numero(valor)      -> float desde texto/numero en formato colombiano o
                        ingles ("1.234,56", "1,234.56", "$ 1.000"); 0.0 si
                        esta vacio o no es un numero.
  formato_cop(valor) -> "$1.234.567,89" (formato de pesos colombianos).
  CERO, CENTAVO      -> Decimal("0"), Decimal("0.01").
  a_centavos(v)      -> Decimal al centavo, mitad hacia arriba (v6.16).

Depende de: (solo biblioteca estandar / terceros)
"""

import re
from decimal import ROUND_HALF_UP, Decimal


# ============================================================
# CONCILIACION BANCARIA: EXTRACTO (PDF) vs. LIBRO DE BANCOS HELISA (PDF)
# ============================================================
# Entradas : extracto bancario en PDF (cualquier banco) y libro de caja
#            bancos de HELISA en PDF.
# Salida   : libro Excel con el analisis de conciliacion.
# Todo se procesa localmente, sin enviar informacion a servicios externos.
#
# Como se hace escalable a cualquier banco:
#   * El extracto se lee por la ESTRUCTURA de la tabla (fecha al inicio de
#     la fila, importes a la derecha, saldo corrido si existe), no con un
#     lector fijo por banco. El nombre del banco solo se usa para rotular.
#   * Todo se valida contra el resumen impreso en el propio extracto.
#   * Los conceptos se clasifican buscando PALABRAS CLAVE contenidas
#     (IVA, ICA, impuesto, comision...), editables en CATEGORIAS.
CENTAVO = Decimal("0.01")


CERO = Decimal("0")


def a_centavos(valor):
    """Decimal redondeado al centavo, mitad hacia arriba (como Excel y la
    practica contable). Un float se toma por su representacion decimal
    (2.675 -> 2,68), no por su binario (2,67499999...)."""
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor if valor is not None else 0))
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def formato_cop(valor):
    valor = a_centavos(valor)
    signo = "-" if valor < 0 else ""
    entero, decimales = f"{abs(valor):.2f}".split(".")
    entero = f"{int(entero):,}".replace(",", ".")
    return f"{signo}${entero},{decimales}"


def numero(valor):
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    if re.fullmatch(r"-?[\d,]*\.\d+|-?\d+", texto):
        return float(texto.replace(",", ""))
    if re.fullmatch(r"-?[\d.]*,\d+", texto):
        return float(texto.replace(".", "").replace(",", "."))
    try:
        return float(texto)
    except ValueError:
        return 0.0
