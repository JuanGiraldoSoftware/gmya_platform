"""Calculos estadisticos de apoyo para los graficos (v6.16, sin Streamlit).

Contrato:
  porcentajes(valores, decimales=1) -> [float] que suman EXACTAMENTE 100
      (metodo del mayor residuo). Asi una leyenda nunca dice 93 % + 6 % +
      0 % = 99 % ni muestra 0 % para una cantidad que no es cero.
  texto_porcentaje(p, valor) -> "0,4 %", "<0,1 %" (si valor != 0 y p
      redondea a 0) o "—" si no hay total.
  TRAMOS_ANTIGUEDAD: tramos de vencimiento usados en cartera y cuentas por
      pagar en Colombia: al dia, 1-30, 31-60, 61-90, 91-180, mas de 180.
  antiguedad(docs, fecha, valor, vence) -> [{"etiqueta", "valor", "n",
      "tramo"}] uno por tramo (todos, aunque esten en 0). docs: iterable;
      valor y vence: funciones doc -> numero / fecha (None = sin fecha:
      tramo "Sin vencimiento"). Dias vencidos = fecha - vence (dias
      calendario); vence el mismo dia = al dia.
  top_n(pares, n=10, otros="Otros") -> los n mayores por valor absoluto y
      una fila "Otros (k)" con el resto (suma exacta).
  concentracion(valores, umbral=0.8) -> (k, total) cuantos elementos
      (ordenados de mayor a menor) acumulan el umbral del total (Pareto).
Depende de: (solo biblioteca estandar)
"""

import math

TRAMOS_ANTIGUEDAD = [
    ("al_dia", "Al día", None, 0),
    ("d30", "1 – 30 días", 1, 30),
    ("d60", "31 – 60 días", 31, 60),
    ("d90", "61 – 90 días", 61, 90),
    ("d180", "91 – 180 días", 91, 180),
    ("mas", "Más de 180 días", 181, None),
]


def porcentajes(valores, decimales=1):
    valores = [abs(float(v or 0)) for v in valores]
    total = sum(valores)
    if not total:
        return [0.0 for _ in valores]
    escala = 10 ** decimales
    exactos = [v / total * 100 * escala for v in valores]
    bases = [math.floor(x) for x in exactos]
    faltan = int(round(100 * escala - sum(bases)))
    orden = sorted(range(len(valores)), key=lambda i: exactos[i] - bases[i],
                   reverse=True)
    for i in orden[:max(faltan, 0)]:
        bases[i] += 1
    return [b / escala for b in bases]


def texto_porcentaje(p, valor=None, decimales=1):
    if p is None:
        return "—"
    if valor and not p:
        return "<" + f"{10 ** -decimales:.{decimales}f}".replace(".", ",") \
            + " %"
    texto = f"{p:.{decimales}f}".replace(".", ",")
    if texto.endswith(",0"):
        texto = texto[:-2]
    return f"{texto} %"


def _tramo(dias):
    for clave, _, desde, hasta in TRAMOS_ANTIGUEDAD:
        if desde is None and dias <= 0:
            return clave
        if desde is not None and dias >= desde and (hasta is None
                                                     or dias <= hasta):
            return clave
    return "al_dia"


def antiguedad(docs, fecha, valor, vence):
    acum = {c: [0.0, 0] for c, *_ in TRAMOS_ANTIGUEDAD}
    sin = [0.0, 0]
    for d in docs:
        v = float(valor(d) or 0)
        f = vence(d)
        if not f:
            sin[0] += v
            sin[1] += 1
            continue
        k = _tramo((fecha - f).days)
        acum[k][0] += v
        acum[k][1] += 1
    salida = [{"tramo": c, "etiqueta": e, "valor": round(acum[c][0], 2),
               "n": acum[c][1]} for c, e, *_ in TRAMOS_ANTIGUEDAD]
    if sin[1]:
        salida.append({"tramo": "sin", "etiqueta": "Sin vencimiento",
                       "valor": round(sin[0], 2), "n": sin[1]})
    return salida


def top_n(pares, n=10, otros="Otros"):
    pares = sorted(((e, float(v or 0)) for e, v in pares),
                   key=lambda x: -abs(x[1]))
    if len(pares) <= n + 1:
        return pares
    resto = pares[n:]
    return pares[:n] + [(f"{otros} ({len(resto)})",
                         round(sum(v for _, v in resto), 2))]


def concentracion(valores, umbral=0.8):
    vals = sorted((abs(float(v or 0)) for v in valores), reverse=True)
    total = sum(vals)
    if not total:
        return 0, len(vals)
    acum = 0.0
    for i, v in enumerate(vals, 1):
        acum += v
        if acum >= total * umbral - 1e-9:
            return i, len(vals)
    return len(vals), len(vals)
