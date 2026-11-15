"""Sugerencias para explicar diferencias (digitos transpuestos, ceros de mas,
retenciones, GMF, comisiones...).

Contrato:
  generar_sugerencias(analisis) -> lista de hipotesis con nivel de
      confianza ("Alta"/"Media"/...).

Depende de: gmya.comun.numeros, gmya.modulos.bancos.lectura, gmya.modulos.bancos.conciliacion
"""

import datetime
from collections import defaultdict
from decimal import Decimal
from itertools import combinations

from gmya.comun.numeros import CENTAVO, CERO, formato_cop
from gmya.modulos.bancos.lectura import (
    CATEGORIAS, es_cargo_bancario, etiqueta_dias, texto_comparable,
)
from gmya.modulos.bancos.conciliacion import sumar


# ------------------------------------------------------------
# Sugerencias: buscar la causa probable de cada partida que no cuadra
# ------------------------------------------------------------
# Despues del emparejamiento quedan partidas del extracto sin libro,
# registros de HELISA sin extracto y diferencias de valor. Aqui se prueban
# hipotesis contables tipicas, en orden de confianza, y para cada una se
# propone que hacer y, cuando aplica, el ajuste contable sugerido.
# Cada sugerencia guarda los CALCULOS que se hicieron (sumas, restas,
# comparaciones), los que explican la diferencia y los descartados, para
# que el contador pueda seguir el razonamiento en la hoja "Análisis".
CONTRAPARTIDAS = {
    "gmf": "5115 Impuestos asumidos – GMF 4x1000",
    "comision": "530515 Comisiones / 530505 Gastos bancarios",
    "iva_bancario": "2408 IVA descontable (o mayor valor del gasto 5305)",
    "rendimientos": "421005 Ingresos financieros – intereses",
    "impuestos": "2404 / 2408 / 2365 Impuestos y retenciones por pagar",
    "seguridad_social": "2370 Retenciones y aportes de nómina",
    "nomina": "2505 Salarios por pagar",
    "proveedores": "2205 Proveedores nacionales",
    "servicios_publicos": "2335 Costos y gastos por pagar",
    "efectivo": "1105 Caja",
    "tarjeta": "Gasto o cuenta por pagar según soporte de la compra",
}
CONTRAPARTIDA_INGRESO = "1305 Clientes / cuenta del tercero que consignó"
CONTRAPARTIDA_EGRESO = "Cuenta del tercero beneficiario (por identificar)"
CONFIANZA_ORDEN = {"Alta": 3, "Media": 2, "Baja": 1}
TARIFAS_RETENCION = [Decimal(x) for x in (
    "0.001", "0.004", "0.008", "0.01", "0.015", "0.02", "0.025", "0.035",
    "0.04", "0.06", "0.07", "0.1", "0.11", "0.15", "0.19")]

SI = "✔ EXPLICA"
NO = "✘ DESCARTADA"
DATO = "• DATO"


def _digitos(valor):
    return f"{abs(valor):.2f}".replace(".", "").lstrip("0")


def _pct(valor):
    return f"{valor * 100:.2f}".replace(".", ",") + " %"


def _num(valor):
    """Numero con separadores colombianos y decimales solo si los hay."""
    valor = Decimal(valor).quantize(CENTAVO)
    texto = formato_cop(abs(valor)).replace("$", "")
    texto = texto[:-3] if texto.endswith(",00") else texto
    # Negativos entre parentesis para que las operaciones se lean bien:
    # 800.000 + (-800.000)
    return f"(-{texto})" if valor < 0 else texto


def analizar_diferencia(valor_banco, valor_libro, tolerancia):
    """
    Prueba, una por una, las causas tipicas de que el mismo movimiento
    tenga valores distintos. Devuelve (hipotesis | None, pruebas) donde
    pruebas = [(prueba, operacion, resultado, estado)].
    La primera prueba que explica la diferencia es la hipotesis.
    """
    a, b = abs(valor_banco), abs(valor_libro)
    d = a - b
    pruebas = [("Diferencia a explicar",
                f"{_num(a)} (extracto) − {_num(b)} (HELISA)",
                f"{_num(d)}", DATO)]
    hipotesis = None

    def registrar(prueba, operacion, resultado, explica, candidata):
        nonlocal hipotesis
        pruebas.append((prueba, operacion, resultado, SI if explica else NO))
        if explica and hipotesis is None:
            hipotesis = candidata

    if d == 0:
        return None, pruebas

    registrar("Redondeo", f"|{_num(d)}| ≤ tolerancia {_num(tolerancia)}",
              "Sí" if abs(d) <= tolerancia else "No",
              abs(d) <= tolerancia,
              ("REDONDEO", f"Diferencia de {formato_cop(abs(d))}, dentro de "
               "la tolerancia de redondeo.", "Alta"))

    mismos = bool(a and b and sorted(_digitos(a)) == sorted(_digitos(b)))
    nueve = (abs(d) * 100) % 9 == 0
    registrar("Dígitos invertidos (transposición)",
              f"Dígitos ordenados de {_num(a)} y {_num(b)} · "
              f"{_num(abs(d))} ÷ 9 = {_num(abs(d) / 9)}",
              ("Mismos dígitos" if mismos else "Dígitos distintos") +
              (" · división exacta" if nueve else " · división no exacta"),
              mismos and nueve,
              ("ERROR DE DIGITACIÓN", "Los dos valores tienen los mismos "
               "dígitos en distinto orden (transposición): "
               f"{formato_cop(a)} en el banco vs {formato_cop(b)} en "
               "HELISA.", "Alta"))

    razon = (a / b) if b else Decimal(0)
    ceros = next((k for k in (10, 100, 1000)
                  if b and (a == b * k or b == a * k)), None)
    registrar("Ceros de más o de menos",
              f"{_num(a)} ÷ {_num(b)}",
              f"{razon:.4f}".replace(".", ","),
              ceros is not None,
              ("ERROR DE DIGITACIÓN", f"Un valor es el otro con ceros de "
               f"más o de menos (x{ceros}).", "Media"))

    mismo_largo = len(_digitos(a)) == len(_digitos(b))
    registrar("Diferencia múltiplo de 9 (dígito mal digitado)",
              f"{_num(abs(d))} ÷ 9 = {_num(abs(d) / 9)}",
              ("Exacta" if nueve else "No exacta") +
              ("" if mismo_largo or not nueve else
               ", pero los valores no tienen la misma cantidad de dígitos"),
              nueve and mismo_largo,
              ("ERROR DE DIGITACIÓN", "La diferencia es múltiplo de 9, "
               "señal típica de un dígito invertido o mal digitado.",
               "Media"))

    base = min(a, b)
    gmf = (base * Decimal("0.004")).quantize(CENTAVO)
    registrar("4x1000 (GMF) incluido en el valor",
              f"{_num(base)} × 0,004 = {_num(gmf)}",
              f"vs diferencia {_num(abs(d))}",
              bool(base) and abs(abs(d) - gmf) <= 1,
              ("4X1000 INCLUIDO", "La diferencia equivale al 4x1000 (GMF) "
               "del valor: uno de los dos documentos lo incluyó dentro del "
               "movimiento.", "Media"))

    if base:
        porcentaje = abs(d) / base
        tarifa = min(TARIFAS_RETENCION, key=lambda t: abs(t - porcentaje))
        calculado = (base * tarifa).quantize(CENTAVO)
        registrar("Retención, descuento o IVA",
                  f"{_num(abs(d))} ÷ {_num(base)} = {_pct(porcentaje)} · "
                  f"tarifa más cercana {_pct(tarifa)}: {_num(base)} × "
                  f"{_pct(tarifa)} = {_num(calculado)}",
                  f"vs diferencia {_num(abs(d))}",
                  abs(abs(d) - calculado) <= 1,
                  ("RETENCIÓN O DESCUENTO", f"La diferencia equivale al "
                   f"{_pct(tarifa)} del valor: posible retención, descuento "
                   "o IVA no registrado en el mismo comprobante.", "Media"))
    return hipotesis, pruebas


def hipotesis_diferencia(valor_banco, valor_libro, tolerancia):
    """Compatibilidad: solo la hipotesis de analizar_diferencia."""
    return analizar_diferencia(valor_banco, valor_libro, tolerancia)[0]


def _efecto_libro(diferencia_banco_menos_libro, contrapartida, concepto,
                  fecha, soporte, cuenta_banco):
    """Ajuste para que HELISA refleje lo que muestra el banco."""
    d = diferencia_banco_menos_libro
    if d == 0:
        return None
    if d > 0:
        debito, credito = cuenta_banco, contrapartida
    else:
        debito, credito = contrapartida, cuenta_banco
    return {"fecha": fecha, "concepto": concepto, "debito": debito,
            "credito": credito, "valor": abs(d), "efecto": d,
            "soporte": soporte}


def generar_sugerencias(analisis):
    movs, lib = analisis["movs"], analisis["libro_movs"]
    parametros = analisis["parametros"]
    ventana = int(parametros["ventana_dias"])
    tolerancia = Decimal(str(parametros["tolerancia_redondeo"]))
    inicio, fin = analisis["extracto"]["periodo"]
    seccion = analisis["seccion"]
    cuenta_banco = ("1110/1120 Bancos – " + (seccion["etiqueta"] or
                                             seccion["cuenta"] or
                                             "cuenta del extracto")).strip()

    for m in movs + lib:
        m["sugerencias"] = []
    sugerencias = []

    def ubic(m):
        return m.get("ubicacion") or ""

    def ref_ext(m):
        return f"{m['descripcion']} ({ubic(m)})" if ubic(m) else \
            m["descripcion"]

    def ref_lib(l):
        texto = f"{l['tipo']} {l['numero']} {l['tercero']}".strip()
        return f"{texto} ({ubic(l)})" if ubic(l) else texto

    def linea_ext(m):
        return (f"«{m['descripcion']}» del {m['fecha']:%d/%m/%Y} por "
                f"{formato_cop(m['valor'])}" +
                (f" ({ubic(m)} del extracto)" if ubic(m) else ""))

    def linea_lib(l):
        return (f"{l['tipo']} {l['numero']} «{l['tercero']}» del "
                f"{l['fecha']:%d/%m/%Y} por {formato_cop(l['valor'])}" +
                (f" ({ubic(l)} de HELISA)" if ubic(l) else ""))

    def que_no_cuadra(extracto, libro):
        if extracto and libro:
            return ("El extracto muestra " + "; ".join(
                linea_ext(m) for m in extracto) + ". HELISA muestra "
                + "; ".join(linea_lib(l) for l in libro) + ".")
        if extracto:
            return ("Está en el extracto y NO en HELISA: " + "; ".join(
                linea_ext(m) for m in extracto) + ".")
        if libro:
            return ("Está en HELISA y NO en el extracto: " + "; ".join(
                linea_lib(l) for l in libro) + ".")
        return ""

    def mas_parecida(valor, lista, etiqueta):
        """Partida del otro documento con el valor mas cercano."""
        candidatos = [x for x in lista if (x["valor"] > 0) == (valor > 0)]
        if not candidatos:
            return (f"Partida más parecida en el {etiqueta}",
                    "Sin partidas de la misma naturaleza", "—", DATO)
        x = min(candidatos, key=lambda x: abs(abs(x["valor"]) - abs(valor)))
        nombre = (x["descripcion"] if "descripcion" in x
                  else f"{x['tipo']} {x['numero']} {x['tercero']}")
        return (f"Partida más parecida en el {etiqueta}",
                f"{nombre} {formato_cop(x['valor'])} "
                f"({x['fecha']:%d/%m/%Y}, {ubic(x)})",
                f"Diferencia {formato_cop(abs(x['valor']) - abs(valor))}",
                DATO)

    def agregar(tipo, confianza, extracto, libro, explicacion, accion,
                ajustes=(), diferencia=None, calculos=(), que=None):
        ident = f"S{len(sugerencias) + 1:03d}"
        sug = {
            "id": ident, "tipo": tipo, "confianza": confianza,
            "extracto": list(extracto), "libro": list(libro),
            "explicacion": explicacion, "accion": accion,
            "ajustes": [a for a in ajustes if a],
            "valor_extracto": sumar(extracto),
            "valor_libro": sumar(libro),
            "diferencia": diferencia if diferencia is not None else
            sumar(extracto) - sumar(libro),
            # Aporte a la diferencia de saldos (extracto - HELISA)
            "efecto_saldo": sumar(extracto) - sumar(libro),
            "calculos": list(calculos),
            "que_no_cuadra": que if que is not None else
            que_no_cuadra(extracto, libro),
        }
        for x in list(extracto) + list(libro):
            x["sugerencias"].append(ident)
        sugerencias.append(sug)
        return sug

    pend_e = [m for m in movs if m["estado"] == "sin_libro"]
    pend_l = [l for l in lib if l["estado"] == "sin_extracto"]
    usados = set()

    def libres(lista):
        return [x for x in lista if id(x) not in usados]

    def usar(*items):
        for x in items:
            usados.add(id(x))

    # 1) Mismo valor, fecha fuera de la ventana de emparejamiento
    for e in sorted(pend_e, key=lambda m: m["fecha"]):
        if id(e) in usados:
            continue
        candidatos = [l for l in libres(pend_l) if l["valor"] == e["valor"]]
        if candidatos:
            l = min(candidatos, key=lambda l: abs((l["fecha"]
                                                   - e["fecha"]).days))
            dias = abs((l["fecha"] - e["fecha"]).days)
            usar(e, l)
            agregar("FECHA DIFERENTE", "Alta", [e], [l],
                    f"Mismo valor en ambos documentos, con {dias} días de "
                    f"diferencia (la ventana de cruce es de {ventana} días).",
                    "Confirmar que es el mismo movimiento. Si HELISA tiene "
                    "la fecha equivocada, corregirla en el comprobante; si "
                    "son de períodos distintos, es partida conciliatoria.",
                    diferencia=CERO, calculos=[
                        ("Comparar valores", f"{_num(e['valor'])} (extracto) "
                         f"− {_num(l['valor'])} (HELISA)", "0", SI),
                        ("Distancia entre fechas",
                         f"{l['fecha']:%d/%m/%Y} vs {e['fecha']:%d/%m/%Y}",
                         f"{dias} días > ventana de {ventana} días", DATO),
                    ])

    # 2) Naturaleza invertida (debito registrado como credito o al reves)
    for e in libres(pend_e):
        candidatos = [l for l in libres(pend_l) if l["valor"] == -e["valor"]
                      and abs((l["fecha"] - e["fecha"]).days) <= 60]
        if candidatos:
            l = min(candidatos, key=lambda l: abs((l["fecha"]
                                                   - e["fecha"]).days))
            usar(e, l)
            agregar("NATURALEZA INVERTIDA", "Alta", [e], [l],
                    "HELISA registró el mismo valor con la naturaleza "
                    "contraria (" + ("egreso" if l["valor"] < 0 else
                                     "ingreso") + " en lugar de " +
                    ("ingreso" if e["valor"] > 0 else "egreso") + ").",
                    "Reversar el comprobante y registrarlo con la naturaleza "
                    "correcta.",
                    [_efecto_libro(e["valor"] - l["valor"],
                                   f"Contrapartida del {l['tipo']} "
                                   f"{l['numero']}",
                                   f"Corregir naturaleza {l['tipo']} "
                                   f"{l['numero']}", e["fecha"], ref_ext(e),
                                   cuenta_banco)],
                    calculos=[
                        ("Sumar los dos valores (si se anulan, es el mismo "
                         "valor con signo contrario)",
                         f"{_num(e['valor'])} + {_num(l['valor'])}", "0",
                         SI),
                        ("Efecto de corregir HELISA",
                         f"{_num(e['valor'])} − {_num(l['valor'])}",
                         _num(e["valor"] - l["valor"]), DATO),
                    ])

    # 3) Un registro de un lado equivale a la suma de varios del otro
    def buscar_combinacion(objetivo, candidatos, maximo=4):
        candidatos = candidatos[:18]
        for tamano in range(2, min(maximo, len(candidatos)) + 1):
            for combo in combinations(candidatos, tamano):
                if abs(sumar(combo) - objetivo) <= Decimal("0.01"):
                    return combo
        return None

    margen = datetime.timedelta(days=max(ventana, 7))
    for l in sorted(libres(pend_l), key=lambda x: -abs(x["valor"])):
        if id(l) in usados:
            continue
        candidatos = sorted(
            [e for e in libres(pend_e) if (e["valor"] > 0) == (l["valor"] > 0)
             and abs(e["fecha"] - l["fecha"]) <= margen],
            key=lambda e: abs((e["fecha"] - l["fecha"]).days))
        combo = buscar_combinacion(l["valor"], candidatos)
        if combo:
            usar(l, *combo)
            agregar("REGISTRO AGRUPADO EN HELISA", "Alta", combo, [l],
                    f"El comprobante {l['tipo']} {l['numero']} suma "
                    f"{len(combo)} movimientos del extracto.",
                    "No requiere ajuste de valor. Dejar nota del cruce o "
                    "registrar por separado si la política lo exige.",
                    diferencia=CERO, calculos=[
                        ("Sumar movimientos del extracto", " + ".join(
                            _num(e["valor"]) for e in combo),
                         _num(sumar(combo)), DATO),
                        (f"Comparar con {l['tipo']} {l['numero']}",
                         f"{_num(sumar(combo))} − {_num(l['valor'])}", "0",
                         SI),
                        ("Búsqueda realizada", f"Combinaciones de 2 a 4 "
                         f"partidas a ±{margen.days} días", "Encontrada",
                         DATO),
                    ])
    for e in sorted(libres(pend_e), key=lambda x: -abs(x["valor"])):
        if id(e) in usados:
            continue
        candidatos = sorted(
            [l for l in libres(pend_l) if (l["valor"] > 0) == (e["valor"] > 0)
             and abs(l["fecha"] - e["fecha"]) <= margen],
            key=lambda l: abs((l["fecha"] - e["fecha"]).days))
        combo = buscar_combinacion(e["valor"], candidatos)
        if combo:
            usar(e, *combo)
            agregar("MOVIMIENTO BANCARIO AGRUPADO", "Alta", [e], combo,
                    f"El movimiento del banco equivale a {len(combo)} "
                    "registros de HELISA (por ejemplo, una consignación con "
                    "varios recibos).",
                    "No requiere ajuste de valor. Verificar el soporte de la "
                    "consignación o el pago conjunto.", diferencia=CERO,
                    calculos=[
                        ("Sumar registros de HELISA", " + ".join(
                            _num(l["valor"]) for l in combo),
                         _num(sumar(combo)), DATO),
                        ("Comparar con el movimiento del extracto",
                         f"{_num(e['valor'])} − {_num(sumar(combo))}", "0",
                         SI),
                    ])

    # 4) Pendientes de ambos lados con error de digitacion
    for e in libres(pend_e):
        candidatos = []
        for l in libres(pend_l):
            if (l["valor"] > 0) != (e["valor"] > 0):
                continue
            if abs((l["fecha"] - e["fecha"]).days) > max(ventana, 7):
                continue
            hipotesis, pruebas = analizar_diferencia(e["valor"], l["valor"],
                                                     tolerancia)
            if hipotesis and hipotesis[0] == "ERROR DE DIGITACIÓN":
                candidatos.append((abs((l["fecha"] - e["fecha"]).days), l,
                                   hipotesis, pruebas))
        if candidatos:
            _, l, (tipo, explicacion, confianza), pruebas = min(
                candidatos, key=lambda x: x[0])
            usar(e, l)
            d = e["valor"] - l["valor"]
            agregar(tipo, confianza, [e], [l], explicacion,
                    "Corregir el valor del comprobante en HELISA según el "
                    "soporte.",
                    [_efecto_libro(d, f"Contrapartida del {l['tipo']} "
                                      f"{l['numero']}",
                                   f"Corregir valor {l['tipo']} "
                                   f"{l['numero']}", e["fecha"], ref_ext(e),
                                   cuenta_banco)], diferencia=d,
                    calculos=[("Partidas candidatas", "Mismo sentido, "
                               f"±{max(ventana, 7)} días", "Se probó cada "
                               "pareja pendiente", DATO)] + pruebas)

    # 5) Diferencias de valor detectadas en el cruce
    cargos_sueltos = [e for e in libres(pend_e)
                      if es_cargo_bancario(e["categoria"])]
    for m in movs:
        if m["estado"] != "diferencia":
            continue
        l = lib[m["pareja"][0]]
        d = m["valor"] - l["valor"]
        hipotesis, pruebas = analizar_diferencia(m["valor"], l["valor"],
                                                 tolerancia)
        relacionados = []
        cargo = next((c for c in cargos_sueltos if id(c) not in usados and
                      abs(c["valor"]) == abs(d) and
                      abs((c["fecha"] - m["fecha"]).days) <= 3), None)
        pruebas.append(("Cargo bancario suelto igual a la diferencia",
                        f"Cargos sin registrar a ±3 días con valor "
                        f"{_num(abs(d))}",
                        f"«{cargo['descripcion']}»" if cargo else
                        "No hay", SI if (cargo and hipotesis is None)
                        else NO if not cargo else DATO))
        if hipotesis is None and cargo:
            relacionados = [cargo]
            hipotesis = ("DIFERENCIA = CARGO BANCARIO",
                         f"La diferencia coincide con el cargo "
                         f"'{cargo['descripcion']}' del extracto: el "
                         "registro de HELISA lo sumó (o lo omitió) en este "
                         "comprobante.", "Media")
        accion = ("Verificar el soporte y corregir el valor del comprobante "
                  f"{l['tipo']} {l['numero']} en HELISA.")
        if hipotesis is None and "pasarela" in (m.get("nota") or ""):
            # v6.9.2: la pasarela (Bold...) abona la venta neta.
            hipotesis = ("DIFERENCIA = DESCUENTOS DE LA PASARELA",
                         m["nota"], "Media")
            accion = ("Registrar la comisión, el IVA y las retenciones de la "
                      "pasarela según la liquidación del periodo (el recibo "
                      f"{l['tipo']} {l['numero']} quedó por el valor bruto).")
        elif hipotesis is None and m.get("nota"):
            hipotesis = ("DIFERENCIA DE VALOR", m["nota"] + " Ninguna de las "
                         "pruebas (redondeo, digitación, ceros, 4x1000, "
                         "retención, cargo bancario) explica la diferencia.",
                         "Baja")
        if hipotesis is None:
            hipotesis = ("DIFERENCIA DE VALOR", "Ninguna de las pruebas "
                         "(redondeo, digitación, ceros, 4x1000, retención, "
                         "cargo bancario) explica la diferencia. Puede ser "
                         "un pago parcial, un abono a otra factura, un "
                         "interés o sanción, o un error en el soporte.",
                         "Baja")
        tipo, explicacion, confianza = hipotesis
        agregar(tipo, confianza, [m] + relacionados, [l], explicacion,
                accion,
                [_efecto_libro(d, f"Contrapartida del {l['tipo']} "
                                  f"{l['numero']}",
                               f"Ajuste por diferencia {l['tipo']} "
                               f"{l['numero']}", m["fecha"], ref_ext(m),
                               cuenta_banco)], diferencia=d,
                calculos=pruebas)
        usar(*relacionados)

    # 5b) Registros conjuntos con diferencia (gastos bancarios en una nota)
    vistos = set()
    for m in movs:
        if m["estado"] != "agrupado_diferencia" or tuple(m["pareja"]) in \
                vistos:
            continue
        vistos.add(tuple(m["pareja"]))
        grupo = [x for x in movs if x["estado"] == "agrupado_diferencia"
                 and x["pareja"] == m["pareja"]]
        libros = [lib[j] for j in m["pareja"]]
        d = sumar(grupo) - sumar(libros)
        faltante = next((x for x in grupo if x["valor"] == d), None)
        calculos = [
            ("Sumar cargos bancarios del extracto", " + ".join(
                _num(x["valor"]) for x in grupo), _num(sumar(grupo)), DATO),
            ("Sumar nota(s) bancaria(s) de HELISA", " + ".join(
                _num(x["valor"]) for x in libros), _num(sumar(libros)),
             DATO),
            ("Diferencia", f"{_num(sumar(grupo))} − {_num(sumar(libros))}",
             _num(d), DATO),
            ("¿La diferencia es uno de los cargos?", "Comparar "
             f"{_num(d)} con cada cargo del grupo",
             f"Sí: «{faltante['descripcion']}»" if faltante else "No",
             SI if faltante else NO),
        ]
        if faltante:
            tipo, confianza = "CARGO OMITIDO EN NOTA BANCARIA", "Alta"
            explicacion = (f"A la nota bancaria le falta el cargo "
                           f"'{faltante['descripcion']}' "
                           f"({formato_cop(abs(d))}).")
        else:
            tipo, confianza = "NOTA BANCARIA CON DIFERENCIA", "Media"
            explicacion = (f"La nota bancaria registra "
                           f"{formato_cop(abs(sumar(libros)))} y los cargos "
                           f"del extracto suman "
                           f"{formato_cop(abs(sumar(grupo)))}.")
        agregar(tipo, confianza, grupo, libros, explicacion,
                "Ajustar la nota bancaria para que coincida con los cargos "
                "del extracto.",
                [_efecto_libro(d, CONTRAPARTIDAS["comision"],
                               "Ajuste nota bancaria " + ", ".join(
                                   f"{x['tipo']} {x['numero']}"
                                   for x in libros),
                               m["fecha"], ref_ext(m), cuenta_banco)],
                diferencia=d, calculos=calculos)

    busquedas_negativas = [
        ("Mismo valor en otra fecha", "Búsqueda en todo el período",
         "No encontrado", NO),
        ("Mismo valor con signo contrario", "Búsqueda a ±60 días",
         "No encontrado", NO),
        ("Suma de 2 a 4 partidas del otro documento",
         f"Combinaciones a ±{margen.days} días", "No encontrada", NO),
        ("Error de digitación con partida pendiente",
         "Transposición, ceros, múltiplo de 9", "No encontrado", NO),
    ]

    # 6) Registros de HELISA que no estan en el extracto
    for l in libres(pend_l):
        duplicado = next((o for o in lib if o is not l and o["valor"] ==
                          l["valor"] and texto_comparable(o["tercero"]) ==
                          texto_comparable(l["tercero"]) and
                          o["estado"] == "conciliado"), None)
        dias_cierre = (fin - l["fecha"]).days
        calculos = [("Fecha frente al período del extracto",
                     f"{l['fecha']:%d/%m/%Y} vs {inicio:%d/%m/%Y} – "
                     f"{fin:%d/%m/%Y}",
                     ("Posterior al cierre" if dias_cierre < 0 else
                      "Anterior al inicio" if l["fecha"] < inicio else
                      f"{dias_cierre} días antes del cierre"), DATO)]
        calculos += busquedas_negativas
        calculos.append(("Registro igual (valor y tercero) ya conciliado",
                         f"Buscar {_num(l['valor'])} «{l['tercero']}»",
                         f"{duplicado['tipo']} {duplicado['numero']}"
                         if duplicado else "No hay",
                         SI if duplicado else NO))
        calculos.append(mas_parecida(l["valor"], movs, "extracto"))
        if l["fecha"] > fin:
            tipo, confianza = "FUERA DEL PERÍODO", "Alta"
            explicacion = ("La fecha del registro es posterior al cierre "
                           "del extracto.")
            accion = "Partida conciliatoria: cruzar con el extracto del " \
                     "mes siguiente."
        elif l["fecha"] < inicio:
            tipo, confianza = "PERÍODO ANTERIOR", "Media"
            explicacion = ("La fecha del registro es anterior al inicio del "
                           "extracto.")
            accion = "Revisar si quedó pendiente de la conciliación del " \
                     "mes anterior."
        elif duplicado:
            tipo, confianza = "POSIBLE DUPLICADO EN HELISA", "Media"
            explicacion = (f"Mismo valor y tercero que {duplicado['tipo']} "
                           f"{duplicado['numero']}, que sí aparece en el "
                           "extracto.")
            accion = "Si está repetido, anular el comprobante."
        elif l["valor"] < 0 and (dias_cierre <= 5 or
                                 l["tipo"].upper().startswith("CH") or
                                 "CHEQUE" in texto_comparable(
                                     l["tercero"]).upper()):
            tipo, confianza = "CHEQUE O EGRESO EN TRÁNSITO", "Media"
            explicacion = ("Egreso registrado al cierre del mes (o cheque) "
                           "que el banco aún no ha pagado.")
            accion = "Partida conciliatoria: verificar en el extracto del " \
                     "mes siguiente."
        elif l["valor"] > 0 and dias_cierre <= 5:
            tipo, confianza = "CONSIGNACIÓN EN TRÁNSITO", "Media"
            explicacion = ("Ingreso registrado al cierre del mes que el "
                           "banco aún no refleja.")
            accion = "Partida conciliatoria: verificar en el extracto del " \
                     "mes siguiente."
        else:
            tipo, confianza = "REGISTRO SIN SOPORTE BANCARIO", "Baja"
            explicacion = ("No aparece en el extracto del período y ninguna "
                           "búsqueda lo explica. Puede ser: un movimiento "
                           "de otra cuenta bancaria, un pago anulado o no "
                           "ejecutado, un cheque girado hace tiempo y no "
                           "cobrado, o un registro con valor muy distinto "
                           "al real.")
            accion = "Revisar el soporte, la cuenta bancaria usada y si el " \
                     "pago realmente se hizo."
        usar(l)
        ajustes = []
        if tipo == "POSIBLE DUPLICADO EN HELISA":
            ajustes = [_efecto_libro(-l["valor"], f"Contrapartida del "
                                     f"{l['tipo']} {l['numero']}",
                                     f"Anular duplicado {l['tipo']} "
                                     f"{l['numero']}", l["fecha"],
                                     ref_lib(l), cuenta_banco)]
        agregar(tipo, confianza, [], [l], explicacion, accion, ajustes,
                diferencia=-l["valor"], calculos=calculos)

    # 7) Movimientos del extracto que faltan en HELISA
    restantes = libres(pend_e)
    por_categoria = defaultdict(list)
    for e in restantes:
        if es_cargo_bancario(e["categoria"]) or \
                e["categoria"] == "rendimientos":
            por_categoria[(e["categoria"], e["valor"] > 0)].append(e)
    for (categoria, positivo), grupo in sorted(por_categoria.items()):
        usar(*grupo)
        nombre = next(n for i, n, _ in CATEGORIAS if i == categoria)
        if categoria == "rendimientos":
            tipo = "RENDIMIENTOS SIN REGISTRAR"
            accion = "Registrar la nota crédito por rendimientos."
        elif positivo:
            tipo = "REINTEGRO BANCARIO SIN REGISTRAR"
            accion = "Registrar el reintegro del banco."
        else:
            tipo = "NOTA BANCARIA PENDIENTE"
            accion = "Registrar la nota bancaria del período."
        calculos = [
            ("Clasificación por palabras clave", "; ".join(
                f"«{e['descripcion']}»" for e in grupo[:6]) +
             ("…" if len(grupo) > 6 else ""), nombre, DATO),
            ("Sumar cargos del grupo", " + ".join(
                _num(e["valor"]) for e in grupo[:12]) +
             (" + …" if len(grupo) > 12 else ""), _num(sumar(grupo)), DATO),
            ("Nota bancaria en HELISA por ese valor",
             "Buscar registros NB/ND/NC o del banco", "No encontrada", NO),
        ]
        agregar(tipo, "Alta", grupo, [],
                f"{len(grupo)} cargo(s) de '{nombre}' del extracto sin "
                "registro en HELISA.", accion,
                [_efecto_libro(sumar(grupo), CONTRAPARTIDAS.get(
                    categoria, CONTRAPARTIDAS["comision"]),
                    f"{nombre} {etiqueta_dias([e['fecha'] for e in grupo])}",
                    max(e["fecha"] for e in grupo), "Extracto: " + ", ".join(
                        sorted({ubic(e) for e in grupo if ubic(e)})),
                    cuenta_banco)], calculos=calculos)

    for e in libres(pend_e):
        repetido = next((o for o in movs if o is not e and o["valor"] ==
                         e["valor"] and texto_comparable(o["descripcion"]) ==
                         texto_comparable(e["descripcion"]) and
                         abs((o["fecha"] - e["fecha"]).days) <= 3), None)
        contrapartida = CONTRAPARTIDAS.get(
            e["categoria"], CONTRAPARTIDA_INGRESO if e["valor"] > 0
            else CONTRAPARTIDA_EGRESO)
        calculos = [("Clasificación por palabras clave",
                     f"«{e['descripcion']}»", e["categoria_nombre"], DATO)]
        calculos += busquedas_negativas
        calculos.append(("Movimiento igual en el extracto (doble cargo)",
                         f"Mismo valor y descripción a ±3 días",
                         f"Sí: {repetido['fecha']:%d/%m/%Y}" if repetido
                         else "No hay", SI if repetido else NO))
        calculos.append(mas_parecida(e["valor"], lib, "libro"))
        if repetido:
            tipo, confianza = "POSIBLE DOBLE CARGO DEL BANCO", "Media"
            explicacion = ("El extracto trae otro movimiento igual (mismo "
                           "valor y descripción) en fechas cercanas.")
            accion = "Si no corresponde, presentar reclamo al banco; si es " \
                     "válido, registrarlo."
        elif e["categoria"] in CONTRAPARTIDAS:
            tipo = ("INGRESO SIN RECIBO DE CAJA" if e["valor"] > 0 else
                    "PAGO SIN COMPROBANTE DE EGRESO")
            confianza = "Media"
            explicacion = (f"Movimiento de '{e['categoria_nombre']}' sin "
                           "registro en HELISA: la descripción del banco "
                           "permite saber a qué corresponde, pero falta el "
                           "comprobante en HELISA.")
            accion = "Ubicar el soporte y registrar el comprobante."
        else:
            tipo = ("INGRESO NO IDENTIFICADO" if e["valor"] > 0 else
                    "EGRESO NO IDENTIFICADO")
            confianza = "Baja"
            explicacion = ("No se encontró en HELISA ni una partida "
                           "parecida que lo explique. Puede ser: " +
                           ("una consignación de un cliente sin recibo de "
                            "caja, un reintegro o un traslado entre cuentas."
                            if e["valor"] > 0 else
                            "un débito automático, un pago con tarjeta, un "
                            "cobro del banco no reconocido o un traslado "
                            "entre cuentas."))
            accion = ("Identificar el tercero con el banco o la tesorería y "
                      "registrar el comprobante.")
        usar(e)
        agregar(tipo, confianza, [e], [], explicacion, accion,
                [_efecto_libro(e["valor"], contrapartida,
                               f"{tipo.capitalize()}: {e['descripcion']}",
                               e["fecha"], ref_ext(e), cuenta_banco)],
                calculos=calculos)

    # 8) Saldo inicial diferente
    conc = analisis["conc"]
    if conc["diferencia_saldo_inicial"] != 0:
        sug = agregar(
            "SALDO INICIAL DIFERENTE", "Media", [], [],
            f"El saldo inicial de HELISA difiere del extracto en "
            f"{formato_cop(conc['diferencia_saldo_inicial'])}: la "
            "diferencia viene del período anterior.",
            "Revisar la conciliación del mes anterior y sus partidas "
            "pendientes.", diferencia=-conc["diferencia_saldo_inicial"],
            calculos=[("Saldo inicial extracto − saldo inicia HELISA",
                       f"{_num(conc['saldo_ini_ext'])} − "
                       f"{_num(conc['saldo_ini_lib'])}",
                       _num(conc["saldo_ini_ext"] - conc["saldo_ini_lib"]),
                       DATO)],
            que=("Los saldos iniciales no coinciden: extracto "
                 f"{formato_cop(conc['saldo_ini_ext'])}, HELISA "
                 f"{formato_cop(conc['saldo_ini_lib'])}."))
        sug["efecto_saldo"] = conc["saldo_ini_ext"] - conc["saldo_ini_lib"]

    for x in movs + lib:
        x["confianza"] = max((CONFIANZA_ORDEN[s["confianza"]]
                              for s in sugerencias if s["id"] in
                              x["sugerencias"]), default=0)
    return sugerencias
