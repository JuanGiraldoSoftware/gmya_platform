"""Nomina electronica: arma la plantilla de carga (DIAN) de la firma.

Contrato:
  leer_acumulado_ne(contenido) -> {empleados: {cedula: {nombre, conceptos:
      {CONCEPTO: {valor, base, cantidad, horas, naturaleza}}}}, total}:
      el "Acumulado de nomina por concepto y periodo" de HELISA.
  leer_movimiento_ne(contenido) -> {cuentas: {cuenta: nombre}, terceros:
      {cedula: {cuenta: debitos - creditos}}, empresa}: el movimiento /
      balance de prueba de las cuentas del gasto (51) y costo (72/61).
  leer_anterior_ne(contenido) -> {cedula: {fecha_ingreso, fecha_retiro,
      nombre}}: hoja BASE DE DATOS o la plantilla del archivo trabajado
      anterior (de ahi salen las fechas de ingreso, que HELISA no trae).
  armar_nomina_electronica(acumulado, movimiento, fechas, ctx) ->
      {filas, controles, alertas}.
  excel_nomina_electronica(resultado, ctx) -> bytes (.xlsx) de control
      (plantilla + filas TOTAL/CONTROL/DIFERENCIA + hojas CONTROL, BASE DE
      DATOS y ALERTAS).
  excel_nomina_electronica_subir(resultado) -> bytes (.xlsx) del archivo
      plano para subir (solo la plantilla, en valores).
  Funciona con los archivos ORIGINALES de HELISA (acumulado de 28 columnas
  con descuentos en negativo y balance de las cuentas 5105/7205 con
  columnas TIPO/NIVEL/NATURALEZA) o con los "trabajados" (v6.11.1).
REGLAS (como el archivo trabajado de EMPRESA G y EMPRESA H, oct-2026):
  - Una fila por empleado del acumulado. Devengados del MOVIMIENTO (debito
    del mes por empleado en la cuenta de gasto o costo): sueldo, auxilio
    de transporte, horas extras, vacaciones, prima, cesantias, intereses,
    incapacidades, licencias, componente no salarial (la cuenta decide
    el tipo, no el nombre del concepto). Dias, bases, horas y deducciones
    del ACUMULADO (salud, pension, fondo de solidaridad, prestamos,
    retencion).
  - Fila de control: total de la plantilla vs contabilidad / HELISA, la
    diferencia debe dar 0. Nada se inventa: lo que no se reconoce se
    alerta.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.comun.grilla,
gmya.modulos.nomina.plantilla_ne
"""

import datetime
import io
import re
from collections import OrderedDict, defaultdict

from gmya.comun.texto import comparable
from gmya.comun.numeros import formato_cop, numero
from gmya.comun.grilla import leer_grilla
from gmya.modulos.nomina.plantilla_ne import LAYOUT_NE_B64


# ------------------------------------------------------------
# Columnas de la plantilla (letras del archivo de la firma)
# ------------------------------------------------------------
NOTA_NE = "NOMINA DEL MES CON PROVISIONES DE NOMINA"
# Valor que lleva el layout de carga en CQ y CS cuando hay
# fondo de solidaridad pensional.
PORCENTAJE_FSP = 9


def dias360(inicio, fin):
    """DAYS360 de Excel con metodo de EE. UU. (FALSE)."""
    if not (isinstance(inicio, datetime.date) and
            isinstance(fin, datetime.date)):
        return None
    d1, d2 = inicio.day, fin.day
    fin_feb = (inicio.month == 2 and
               (inicio + datetime.timedelta(days=1)).month == 3)
    if d1 == 31 or fin_feb:
        d1 = 30
    if d2 == 31 and d1 >= 30:
        d2 = 30
    return ((fin.year - inicio.year) * 360 + (fin.month - inicio.month) * 30
            + d2 - d1)
# Horas extras y recargos: (patron del concepto) -> (codigo, porcentaje)
TIPOS_HORA = [
    ("EXTRA NOCTURNA DOMINICAL", 6, 150), ("RECARGO NOCTURNO DOMINICAL", 7, 110),
    ("EXTRA DIURNA DOMINICAL", 4, 100), ("RECARGO DIURNO DOMINICAL", 5, 75),
    ("RECARGO DOMINICAL", 5, 75), ("EXTRA NOCTURNA", 2, 75),
    ("RECARGO NOCTURNO", 3, 35), ("EXTRA DIURNA", 1, 25), ("HORA EXTRA", 1, 25),
]
# Cuentas del movimiento -> campo de la plantilla (por nombre de cuenta).
# (clave, patrones, excluir)
CAMPOS_CUENTA = [
    ("intereses", ["INTERESES SOBRE CESANTIAS", "INTERESES DE CESANTIAS",
                   "INT. CESANTIAS"], []),
    ("cesantias", ["CESANTIAS"], ["INTERES"]),
    ("prima", ["PRIMA DE SERVICIOS", "PRIMA"], []),
    ("vacaciones", ["VACACIONES"], []),
    ("aux_transporte", ["AUXILIO DE TRANSPORTE"], []),
    ("aux_conectividad", ["CONECTIVIDAD"], []),
    ("horas_extras", ["HORAS EXTRAS", "RECARGOS"], []),
    ("incapacidad", ["INCAPACIDAD", "ENFERMEDAD GENERAL"], []),
    ("licencia", ["LICENCIA", "PERMISOS REMUNERADOS"], ["NO REMUNERADA"]),
    ("indemnizacion", ["INDEMNIZACION"], []),
    ("bonificacion_retiro", ["BONIFICACION DE RETIRO"], []),
    ("dotacion", ["DOTACION"], []),
    ("no_salarial", ["COMPONENTE NO SALARIAL", "NO SALARIAL"], []),
    ("sueldo", ["SUELDO", "SALARIO"], ["INTEGRAL"]),
]
NOMBRE_CAMPO = {
    "sueldo": "Sueldo", "aux_transporte": "Auxilio de transporte",
    "aux_conectividad": "Auxilio de conectividad",
    "horas_extras": "Horas extras y recargos", "vacaciones": "Vacaciones",
    "prima": "Prima", "cesantias": "Cesantías",
    "intereses": "Intereses de cesantías", "incapacidad": "Incapacidades",
    "licencia": "Licencias", "indemnizacion": "Indemnización",
    "bonificacion_retiro": "Bonificación de retiro", "dotacion": "Dotación",
    "no_salarial": "Componente no salarial",
}
# Campo -> letra de la columna de valor en la plantilla
LETRA_CAMPO = {
    "sueldo": "X", "aux_transporte": "Z", "aux_conectividad": "Z",
    "horas_extras": "AH", "vacaciones": "AM", "prima": "AO",
    "cesantias": "AQ", "intereses": "AS", "incapacidad": "AY",
    "licencia": "BD", "no_salarial": "BP", "dotacion": "CE",
    "bonificacion_retiro": "CH", "indemnizacion": "CI",
}
DEVENGADOS = ["X", "Z", "AA", "AB", "AH", "AM", "AO", "AQ", "AS", "AY", "BD",
              "BE", "BF", "BH", "BI", "BO", "BP", "BQ", "BR", "BT", "BU",
              "BV", "BW", "BY", "CA", "CC", "CE", "CF", "CG", "CH", "CI",
              "CJ"]
DEDUCCIONES = ["CM", "CP", "CR", "CT", "CW", "CY", "CZ", "DC", "DD", "DF",
               "DH", "DJ", "DK", "DL", "DM", "DN", "DO", "DP", "DQ", "DR"]


def _col(letra):
    n = 0
    for ch in letra:
        n = n * 26 + ord(ch) - 64
    return n


def campo_de_cuenta(nombre):
    t = comparable(nombre)
    for clave, patrones, excluir in CAMPOS_CUENTA:
        if any(comparable(x) in t for x in excluir):
            continue
        if any(comparable(p) in t for p in patrones):
            return clave
    return None


def _cedula(v):
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\D", "", str(v or "")).lstrip("0")


def _filas(contenido):
    r = leer_grilla(contenido)
    filas = r[0] if isinstance(r, tuple) else r
    salida = []
    for f in filas:
        if isinstance(f, dict):
            cel = f.get("celdas") or []
            fila = [None] * (max((c["col"] for c in cel), default=0))
            for c in cel:
                fila[c["col"] - 1] = c["valor"]
            salida.append(fila)
        else:
            salida.append(list(f))
    return salida


def _t(v):
    return "" if v is None else str(v).strip()


def _redondo(v):
    v = round(float(v or 0), 2)
    return int(v) if float(v).is_integer() else v


# ------------------------------------------------------------
# Lectura
# ------------------------------------------------------------
def leer_acumulado_ne(contenido):
    filas = _filas(contenido)
    titulo = next((i for i, f in enumerate(filas[:15])
                   if "IDENTIFICACION" in [comparable(_t(v)) for v in f]
                   and "CONCEPTO" in [comparable(_t(v)) for v in f]), None)
    if titulo is None:
        raise ValueError("No parece el acumulado de nómina de HELISA (no se "
                         "encontraron las columnas IDENTIFICACION y "
                         "CONCEPTO).")
    cab = [comparable(_t(v)) for v in filas[titulo]]

    def col(*n):
        for x in n:
            if comparable(x) in cab:
                return cab.index(comparable(x))
        return None
    c = {"id": col("IDENTIFICACION"), "nom": col("NOMBRE COMPLETO", "NOMBRE"),
         "con": col("CONCEPTO"), "nat": col("NATURALEZA"),
         "base": col("BASE"), "cant": col("CANTIDAD"),
         "val": col("VALORPAGO", "VALOR PAGO", "VALOR"), "horas": col("HORAS"),
         "fecha": col("FECHA DE PAGO")}
    empleados = OrderedDict()
    fechas = set()
    for f in filas[titulo + 1:]:
        def v(k):
            i = c.get(k)
            return f[i] if i is not None and i < len(f) else None
        ced = _cedula(v("id"))
        concepto = comparable(_t(v("con")))
        if not ced or not concepto:
            continue
        e = empleados.setdefault(ced, {"cedula": ced, "nombre": _t(v("nom")),
                                       "conceptos": OrderedDict()})
        x = e["conceptos"].setdefault(concepto, {
            "valor": 0.0, "base": 0.0, "cantidad": 0.0, "horas": 0.0,
            "naturaleza": comparable(_t(v("nat")))})
        x["valor"] += abs(float(numero(v("val")) or 0))
        x["base"] += float(numero(v("base")) or 0)
        x["cantidad"] += float(numero(v("cant")) or 0)
        x["horas"] += float(numero(v("horas")) or 0)
        fe = v("fecha")
        if hasattr(fe, "date"):
            fechas.add(fe.date())
    if not empleados:
        raise ValueError("El acumulado de nómina no trae empleados.")
    return {"empleados": empleados, "fechas_pago": sorted(fechas)}


def leer_movimiento_ne(contenido):
    """Movimiento / balance de prueba con terceros. Acepta el formato
    CUENTA | NIT | NOMBRE | SALDO INICIAL | DEBITO | CREDITO | SALDO FINAL
    (Excel de HELISA) y el de terceros 'nombre (Id. cedula)'."""
    filas = _filas(contenido)
    cuentas, terceros, nombres = {}, defaultdict(lambda: defaultdict(float)), {}
    cuenta_actual, empresa = None, ""
    totales_cuenta = {}
    c_deb = c_cre = None
    for f in filas[:15]:
        cab = [comparable(_t(v)) for v in f]
        if "DEBITO" in cab and "CREDITO" in cab:
            c_deb, c_cre = cab.index("DEBITO"), cab.index("CREDITO")
            break
        if "DEBITOS" in cab and "CREDITOS" in cab:
            c_deb, c_cre = cab.index("DEBITOS"), cab.index("CREDITOS")
            break

    def movimiento_fila(f, nums):
        # Por encabezado (DEBITO / CREDITO); si no hay, el formato de
        # HELISA: saldo inicial, debitos, creditos, nuevo saldo.
        if c_deb is not None and c_cre < len(f):
            return round(float(numero(f[c_deb]) or 0) -
                         float(numero(f[c_cre]) or 0), 2)
        return round(float(nums[-3]) - float(nums[-2]), 2)
    for f in filas:
        textos = [(j, v) for j, v in enumerate(f) if v not in (None, "")]
        if not textos:
            continue
        nums = [v for _, v in textos if isinstance(v, (int, float))]
        primero = _t(textos[0][1])
        m = re.match(r"^(\d{4,10})(?:\s+(.*))?$", primero)
        if not empresa and re.search(r"S\.?A\.?S|LTDA", primero.upper()):
            empresa = primero
        if m and len(nums) >= 3:
            cta = m.group(1)
            resto = [_t(v) for j, v in textos[1:] if isinstance(v, str)]
            nit = _cedula(textos[1][1]) if len(textos) > 1 and not \
                isinstance(textos[1][1], str) else ""
            if not nit and len(textos) > 1 and isinstance(textos[1][1], str) \
                    and re.fullmatch(r"[\d.\-]{5,}", textos[1][1].strip()):
                nit = _cedula(textos[1][1])
            mov = movimiento_fila(f, nums)
            if nit:
                terceros[nit][cta] += mov
                nombres.setdefault(nit, resto[0] if resto else "")
            else:
                cuentas[cta] = (m.group(2) or (resto[0] if resto else "")
                                ).strip()
                totales_cuenta[cta] = mov
                cuenta_actual = cta
            continue
        t = re.search(r"\(Id\.\s*([\d.\-]+)\)", primero)
        if t and cuenta_actual and len(nums) >= 3:
            ced = _cedula(t.group(1))
            terceros[ced][cuenta_actual] += movimiento_fila(f, nums)
            nombres.setdefault(ced, re.sub(r"\(Id\..*", "", primero).strip())
    if not cuentas:
        raise ValueError("No se encontraron cuentas en el movimiento "
                         "contable.")
    return {"cuentas": cuentas, "terceros": {k: dict(v) for k, v in
                                              terceros.items()},
            "nombres": nombres, "totales_cuenta": totales_cuenta,
            "empresa": empresa}


def leer_anterior_ne(contenido):
    """Fechas de ingreso y retiro del archivo trabajado anterior: hoja con
    IDENTIFICACION + FECHA DE INGRESO (BASE DE DATOS) o la plantilla
    (columna D identificacion, L fecha ingreso, M fecha retiro)."""
    from openpyxl import load_workbook
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        libro = load_workbook(io.BytesIO(contenido), data_only=True)
    fechas = {}
    for ws in libro.worksheets:
        filas = list(ws.iter_rows(values_only=True))
        for i, f in enumerate(filas[:10]):
            cab = [comparable(_t(v)) for v in f]
            c_id = next((j for j, t in enumerate(cab)
                         if t.startswith("IDENTIFICACION")), None)
            c_ing = next((j for j, t in enumerate(cab)
                          if t.startswith("FECHA DE INGRESO")), None)
            if c_id is None or c_ing is None:
                continue
            c_ret = next((j for j, t in enumerate(cab)
                          if t.startswith("FECHA DE RETIRO")), None)
            c_nom = next((j for j, t in enumerate(cab)
                          if t.startswith("NOMBRE")), None)
            for f2 in filas[i + 1:]:
                ced = _cedula(f2[c_id] if c_id < len(f2) else None)
                ing = f2[c_ing] if c_ing < len(f2) else None
                if not ced or not hasattr(ing, "year"):
                    continue
                ret = f2[c_ret] if c_ret is not None and c_ret < len(f2) \
                    else None
                previo = fechas.get(ced)
                # Con varios contratos se toma el mas reciente.
                if previo and previo["fecha_ingreso"] >= ing.date():
                    continue
                fechas[ced] = {
                    "fecha_ingreso": ing.date(),
                    "fecha_retiro": ret.date() if hasattr(ret, "year")
                    else None,
                    "nombre": _t(f2[c_nom]) if c_nom is not None else ""}
            break
        if fechas:
            continue
        # Plantilla: fila 3 con "Identificación del trabajador".
        if len(filas) > 6 and any("IDENTIFICACION DEL" in comparable(_t(v))
                                  for v in (filas[2] or [])):
            for f2 in filas[6:]:
                ced = _cedula(f2[_col("D") - 1] if len(f2) >= 4 else None)
                ing = f2[_col("L") - 1] if len(f2) >= 12 else None
                if ced and hasattr(ing, "year") and ced not in fechas:
                    ret = f2[_col("M") - 1] if len(f2) >= 13 else None
                    fechas[ced] = {"fecha_ingreso": ing.date(),
                                   "fecha_retiro": ret.date()
                                   if hasattr(ret, "year") else None,
                                   "nombre": ""}
    return fechas


# ------------------------------------------------------------
# Armado
# ------------------------------------------------------------
def _concepto_con(conceptos, *patrones, excluir=()):
    salida = []
    for nombre, x in conceptos.items():
        if any(e in nombre for e in excluir):
            continue
        if any(p in nombre for p in patrones):
            salida.append((nombre, x))
    return salida


def armar_nomina_electronica(acumulado, movimiento, fechas, ctx):
    """ctx: inicio, fin (periodo), fecha_emision, fecha_pago."""
    inicio, fin = ctx["inicio"], ctx["fin"]
    alertas = []
    cuentas = movimiento["cuentas"]
    campo_cuenta = {c: campo_de_cuenta(n) for c, n in cuentas.items()}
    filas = []
    usados = defaultdict(float)
    por_valor = {}
    for ced, e in acumulado["empleados"].items():
        con = e["conceptos"]
        mov = movimiento["terceros"].get(ced, {})
        fila = OrderedDict()
        fila.update({"A": 102, "B": 4, "C": "COP", "D": int(ced) if
                     ced.isdigit() else ced, "E": ctx["fecha_emision"],
                     "G": NOTA_NE})
        f = fechas.get(ced) or {}
        if f.get("fecha_ingreso"):
            fila["L"] = f["fecha_ingreso"]
        else:
            alertas.append(f"{e['nombre']} ({ced}): no se encontró la fecha "
                           "de ingreso (carga el archivo trabajado anterior o "
                           "escríbela en la tabla).")
        if f.get("fecha_retiro") and inicio <= f["fecha_retiro"] <= fin:
            fila["M"] = f["fecha_retiro"]
        fila.update({"N": inicio, "O": fin, "Q": 1, "R": 31, "S": 0, "T": 1,
                     "U": 0, "V": ctx.get("fecha_pago") or fin})
        # Devengados desde la contabilidad (por cuenta).
        valores = defaultdict(float)
        sin_campo = []
        for cta, v in mov.items():
            if not v:
                continue
            campo = campo_cuenta.get(cta)
            if campo is None and cta.startswith(("51", "52", "61", "72")):
                # El nombre de la cuenta no dice que es (p. ej. 510110
                # REMUNERACION POR TRABAJO OCASIONAL): se usa el concepto
                # del acumulado con el MISMO valor para este empleado, si
                # es unico.
                iguales = [n for n, x in con.items()
                           if x["naturaleza"] != "DESCUENTO" and
                           abs(x["valor"] - v) <= 0.005 and
                           campo_de_cuenta(n)]
                if len(iguales) == 1:
                    campo = campo_de_cuenta(iguales[0])
                    campo_cuenta_emp = f"{cta} {cuentas.get(cta, '')}"
                    alertas.append(
                        f"{e['nombre']} ({ced}): la cuenta "
                        f"{campo_cuenta_emp} ({formato_cop(v)}) se tomó como "
                        f"«{iguales[0]}» del acumulado (mismo valor). "
                        "Confirmar.")
                    por_valor[cta] = campo
            if campo is None:
                if cta.startswith(("51", "52", "61", "72")):
                    sin_campo.append(f"{cta} {cuentas.get(cta, '')} "
                                     f"({formato_cop(v)})")
                continue
            valores[campo] += v
            usados[cta] += v
        if sin_campo:
            alertas.append(f"{e['nombre']} ({ced}): cuentas del movimiento "
                           "que no se reconocen y no se llevan a la "
                           "plantilla: " + ", ".join(sin_campo) + ".")
        sueldo = _concepto_con(con, "SUELDO", "SALARIO")
        dias = round(sum(x["cantidad"] for _, x in sueldo))
        if dias:
            fila["W"] = dias
        else:
            alertas.append(f"{e['nombre']} ({ced}): el acumulado no trae los "
                           "días del sueldo (CANTIDAD).")
        for campo, letra in LETRA_CAMPO.items():
            if valores.get(campo):
                fila[letra] = _redondo(fila.get(letra, 0) +
                                       valores[campo])
        # Horas extras: cantidad y porcentaje desde el acumulado.
        if valores.get("horas_extras"):
            horas = _concepto_con(con, "EXTRA", "RECARGO")
            if horas:
                nombre_h = horas[0][0]
                tipo = next(((c, p) for pat, c, p in TIPOS_HORA
                             if pat in nombre_h), None)
                cant = sum(x["horas"] or x["cantidad"] for _, x in horas)
                if tipo:
                    # v6.11.1: el layout que se sube deja el
                    # codigo del tipo de hora (AC) vacio; solo el porcentaje.
                    fila["AG"] = tipo[1]
                fila["AF"] = _redondo(cant)
                if len({h[0] for h in horas}) > 1:
                    alertas.append(f"{e['nombre']} ({ced}): tiene varios "
                                   "tipos de horas extras/recargos (" +
                                   ", ".join(h[0] for h in horas) + "); la "
                                   "plantilla lleva uno: revisar.")
        if "AM" in fila:
            fila["AI"], fila["AL"] = 1, fila.get("W")
        if "AO" in fila:
            fila["AN"] = fila.get("W")
        if "AQ" in fila or "AS" in fila:
            fila["AR"], fila["AT"] = 12, fila.get("W")
        if "AY" in fila:
            inc = _concepto_con(con, "INCAPACIDAD", "INACTIVIDAD")
            fila["AU"] = 1
            fila["AX"] = _redondo(sum(x["cantidad"] for _, x in inc)) or None
        if "BD" in fila:
            lic = _concepto_con(con, "LICENCIA", "INACTIVIDAD", "PERMISO")
            fila["AZ"] = 2
            fila["BC"] = _redondo(sum(x["cantidad"] for _, x in lic)) or None
        if "BP" in fila:
            fila["BN"] = "COMPONENTE NO SALARIAL"
        # Deducciones desde el acumulado.
        salud = _concepto_con(con, "SALUD")
        if salud:
            fila["CK"] = 4
            fila["CL"] = _redondo(sum(x["base"] for _, x in salud))
            fila["CM"] = _redondo(sum(x["valor"] for _, x in salud))
        pension = _concepto_con(con, "PENSION", excluir=("VOLUNTARIA",))
        if pension:
            fila["CN"] = 4
            fila["CO"] = _redondo(sum(x["base"] for _, x in pension))
            fila["CP"] = _redondo(sum(x["valor"] for _, x in pension))
        else:
            alertas.append(f"{e['nombre']} ({ced}): sin aporte a pensión en "
                           "el acumulado (¿pensionado?). La columna de "
                           "pensión queda vacía: confirmar cómo se reporta.")
        sol = _concepto_con(con, "SOLIDARIDAD")
        if sol:
            total = sum(x["valor"] for _, x in sol)
            mitad = round(total / 2, 2)
            # v6.11.1: el layout que se sube lleva 9 en CQ y CS.
            fila["CQ"], fila["CR"] = PORCENTAJE_FSP, _redondo(mitad)
            fila["CS"], fila["CT"] = PORCENTAJE_FSP, _redondo(total - mitad)
        otros = _concepto_con(con, "PRESTAMO", "LIBRANZA", "EMBARGO",
                              "POLIZA", "DESCUENTO", excluir=("SALUD",
                                                              "PENSION"))
        otros = [(n, x) for n, x in otros if x["valor"]]
        if otros:
            fila["DH"] = _redondo(sum(x["valor"] for _, x in otros))
            fila["DI"] = " / ".join(n for n, _ in otros)
        ret = _concepto_con(con, "RETENCION")
        if ret and sum(x["valor"] for _, x in ret):
            fila["DK"] = _redondo(sum(x["valor"] for _, x in ret))
        conocidos = {"SUELDO", "SALARIO", "SALUD", "PENSION", "SOLIDARIDAD",
                     "PRESTAMO", "LIBRANZA", "EMBARGO", "POLIZA", "DESCUENTO",
                     "RETENCION", "AUXILIO", "COMPONENTE", "EXTRA", "RECARGO",
                     "INCAPACIDAD", "INACTIVIDAD", "LICENCIA", "VACACION",
                     "PRIMA", "CESANTIA", "INDEMNIZACION", "BONIFICACION",
                     "DOTACION", "PERMISO"}
        raros = [n for n, x in con.items() if x["valor"] and
                 not any(k in n for k in conocidos)]
        if raros:
            alertas.append(f"{e['nombre']} ({ced}): conceptos del acumulado "
                           "sin columna en la plantilla: " + ", ".join(raros)
                           + ".")
        # Tiempo laborado (P) como valor: el archivo para subir no lleva
        # formulas.
        if fila.get("L") and fila.get("O"):
            fila["P"] = dias360(fila["L"], fila["O"])
        # Totales
        dev = round(sum(float(fila.get(c) or 0) for c in DEVENGADOS
                        if isinstance(fila.get(c), (int, float))), 2)
        ded = round(sum(float(fila.get(c) or 0) for c in DEDUCCIONES
                        if isinstance(fila.get(c), (int, float))), 2)
        fila["DT"], fila["DU"], fila["DV"] = (_redondo(dev), _redondo(ded),
                                              _redondo(dev - ded))
        # Control por empleado: sueldo del acumulado vs contabilidad.
        s_acu = round(sum(x["valor"] for _, x in sueldo), 2)
        if abs(s_acu - float(fila.get("X") or 0)) > 0.005:
            alertas.append(f"{e['nombre']} ({ced}): sueldo en el acumulado "
                           f"{formato_cop(s_acu)} vs contabilidad "
                           f"{formato_cop(fila.get('X') or 0)}.")
        filas.append({"cedula": ced, "nombre": e["nombre"], "fila": fila})
    for ced in movimiento["terceros"]:
        if ced not in acumulado["empleados"] and any(
                campo_cuenta.get(c) in ("sueldo",) and v
                for c, v in movimiento["terceros"][ced].items()):
            alertas.append(f"{movimiento['nombres'].get(ced, '')} ({ced}) "
                           "tiene sueldo en la contabilidad pero no está en "
                           "el acumulado de nómina.")
    # Controles: plantilla vs contabilidad (todas las cuentas del campo) y
    # deducciones vs acumulado.
    controles = []
    por_campo = defaultdict(float)
    for cta, v in movimiento["totales_cuenta"].items():
        campo = campo_cuenta.get(cta) or por_valor.get(cta)
        if campo and campo in LETRA_CAMPO and len(cta) >= 6 and not any(
                otra != cta and otra.startswith(cta)
                for otra in movimiento["totales_cuenta"]):
            por_campo[LETRA_CAMPO[campo]] += v
    for letra, total in sorted(por_campo.items(), key=lambda x: _col(x[0])):
        plantilla = round(sum(float(f["fila"].get(letra) or 0)
                              for f in filas), 2)
        if not plantilla and not round(total, 2):
            continue
        if campo_por_letra(letra) == "dotacion" and not plantilla:
            continue
        controles.append({"columna": letra, "concepto": nombre_letra(letra),
                          "plantilla": plantilla,
                          "fuente": round(total, 2), "origen": "Contabilidad",
                          "diferencia": round(plantilla - total, 2)})
    for letra, patrones, nombre in (
            ("CM", ("SALUD",), "Salud"), ("CP", ("PENSION",), "Pensión"),
            ("DH", ("PRESTAMO", "LIBRANZA", "EMBARGO", "POLIZA"),
             "Otras deducciones"),
            ("DK", ("RETENCION",), "Retención en la fuente")):
        fuente = round(sum(x["valor"] for e in acumulado["empleados"].values()
                           for n, x in e["conceptos"].items()
                           if any(p in n for p in patrones)
                           and "VOLUNTARIA" not in n), 2)
        plantilla = round(sum(float(f["fila"].get(letra) or 0)
                              for f in filas), 2)
        if fuente or plantilla:
            controles.append({"columna": letra, "concepto": nombre,
                              "plantilla": plantilla, "fuente": fuente,
                              "origen": "Acumulado HELISA",
                              "diferencia": round(plantilla - fuente, 2)})
    for c in controles:
        if abs(c["diferencia"]) > 0.005:
            alertas.append(f"Control {c['concepto']} (columna "
                           f"{c['columna']}): plantilla "
                           f"{formato_cop(c['plantilla'])} vs "
                           f"{c['origen'].lower()} {formato_cop(c['fuente'])}"
                           f" → diferencia {formato_cop(c['diferencia'])}.")
    return {"filas": filas, "controles": controles, "alertas": alertas,
            "cuadra": all(abs(c["diferencia"]) <= 0.005 for c in controles)}


def campo_por_letra(letra):
    return next((c for c, l in LETRA_CAMPO.items() if l == letra), None)


def nombre_letra(letra):
    c = campo_por_letra(letra)
    if letra == "Z":
        return "Auxilio de transporte / conectividad"
    return NOMBRE_CAMPO.get(c, letra)


# ------------------------------------------------------------
# Excel
# ------------------------------------------------------------
def excel_nomina_electronica(resultado, ctx):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter as L
    libro, ws = _libro_layout()
    fino = Side(style="thin", color="999999")
    borde = Border(left=fino, right=fino, top=fino, bottom=fino)
    fecha_fmt = "yyyy-mm-dd"
    primera = 7
    fila = primera
    validacion = validar_filas_ne(resultado)
    for f, v in zip(resultado["filas"], validacion):
        _escribir_fila_layout(ws, fila, f["fila"], v)
        if "L" in f["fila"]:
            ws.cell(fila, _col("P"), f"=DAYS360(L{fila},O{fila},FALSE)")
        ws.cell(fila, _col("DT"), "=" + "+".join(f"{c}{fila}"
                                                 for c in DEVENGADOS))
        ws.cell(fila, _col("DU"), "=" + "+".join(f"{c}{fila}"
                                                 for c in DEDUCCIONES))
        ws.cell(fila, _col("DV"), f"=DT{fila}-DU{fila}")
        fila += 1
    ultima = fila - 1
    negrita = Font(bold=True)
    amarillo = PatternFill("solid", fgColor="FFF2CC")
    # Fila de totales, control y diferencia (como el archivo trabajado).
    f_tot, f_ctl, f_dif = fila, fila + 1, fila + 2
    ws.cell(f_tot, _col("V"), "TOTAL PLANTILLA").font = negrita
    ws.cell(f_ctl, _col("V"), "CONTABILIDAD / HELISA").font = negrita
    ws.cell(f_dif, _col("V"), "DIFERENCIA").font = Font(bold=True,
                                                       color="C00000")
    columnas_total = ["W", "X", "Z", "AF", "AH", "AM", "AO", "AQ", "AS",
                      "AX", "AY", "BC", "BD", "BP", "CE", "CH", "CI", "CL",
                      "CM", "CO", "CP", "CR", "CT", "DH", "DK", "DT", "DU",
                      "DV"]
    for letra in columnas_total:
        c = _col(letra)
        ws.cell(f_tot, c, f"=SUM({letra}{primera}:{letra}{ultima})")
        ws.cell(f_tot, c).font = negrita
        ws.cell(f_tot, c).number_format = "#,##0.##"
    for ctl in resultado["controles"]:
        c = _col(ctl["columna"])
        ws.cell(f_ctl, c, ctl["fuente"]).number_format = "#,##0.##"
        ws.cell(f_dif, c, f"=ROUND({ctl['columna']}{f_tot}-"
                          f"{ctl['columna']}{f_ctl},2)")
        ws.cell(f_dif, c).font = Font(bold=True, color="C00000")
        ws.cell(f_dif, c).number_format = "#,##0.##"
    for r in (f_tot, f_ctl, f_dif):
        for c in range(_col("V"), _col("DV") + 1):
            ws.cell(r, c).fill = amarillo
    ws.freeze_panes = "E7"
    # CONTROL
    hc = libro.create_sheet("CONTROL")
    hc.append(["COLUMNA", "CONCEPTO", "PLANTILLA", "FUENTE", "ORIGEN",
               "DIFERENCIA"])
    for c in resultado["controles"]:
        hc.append([c["columna"], c["concepto"], c["plantilla"], c["fuente"],
                   c["origen"], c["diferencia"]])
    for celda in hc[1]:
        celda.font = negrita
    for letra, ancho in zip("ABCDEF", (10, 36, 18, 18, 20, 16)):
        hc.column_dimensions[letra].width = ancho
    # BASE DE DATOS (fechas usadas)
    hb = libro.create_sheet("BASE DE DATOS")
    hb.append(["NOMBRE COMPLETO", "IDENTIFICACIÓN", "FECHA DE INGRESO",
               "FECHA DE RETIRO"])
    for f in resultado["filas"]:
        hb.append([f["nombre"], f["fila"].get("D"), f["fila"].get("L"),
                   f["fila"].get("M")])
        for c in (3, 4):
            hb.cell(hb.max_row, c).number_format = fecha_fmt
    for celda in hb[1]:
        celda.font = negrita
    for letra, ancho in zip("ABCD", (42, 16, 16, 16)):
        hb.column_dimensions[letra].width = ancho
    # ALERTAS
    ha = libro.create_sheet("ALERTAS")
    for i, a in enumerate(resultado["alertas"] or ["Sin alertas."], 1):
        ha.cell(i, 1, a).alignment = Alignment(wrap_text=True)
    ha.column_dimensions["A"].width = 140
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def _libro_layout():
    """Libro con el layout de carga de la firma tal cual (filas 1 a 6) y la
    fila 7 como modelo de formato de una fila de datos."""
    import base64
    from openpyxl import load_workbook
    libro = load_workbook(io.BytesIO(base64.b64decode(LAYOUT_NE_B64)),
                          rich_text=True)
    return libro, libro.worksheets[0]


AMARILLO_NE = "FFFFFF00"
ROJO_NE = "FFFFC7CE"


def validar_filas_ne(resultado):
    """Columna DW (como la firma: fila pintada + OK). Por empleado:
    {"estado": "OK" | "REVISAR: ...", "novedad": bool}. Novedad = horas
    extras, incapacidad, licencia, otras deducciones, fondo de solidaridad
    o retencion (las filas que la firma revisa y pinta). REVISAR cuando
    el empleado tiene alertas, falta un dato obligatorio o los totales no
    dan."""
    salida = []
    for f in resultado["filas"]:
        d = f["fila"]
        motivos = []
        for letra, nombre in (("L", "fecha de ingreso"), ("X", "sueldo"),
                              ("CL", "base salud"), ("CM", "salud"),
                              ("CO", "base pensión"), ("CP", "pensión")):
            if d.get(letra) in (None, ""):
                motivos.append("falta " + nombre)
        dev = round(sum(float(d.get(c) or 0) for c in DEVENGADOS
                        if isinstance(d.get(c), (int, float))), 2)
        ded = round(sum(float(d.get(c) or 0) for c in DEDUCCIONES
                        if isinstance(d.get(c), (int, float))), 2)
        if (abs(dev - float(d.get("DT") or 0)) > 0.005 or
                abs(ded - float(d.get("DU") or 0)) > 0.005 or
                abs(dev - ded - float(d.get("DV") or 0)) > 0.005):
            motivos.append("totales DT/DU/DV no dan")
        if d.get("BP") and not d.get("BN"):
            motivos.append("BP sin descripción en BN")
        if d.get("DH") and not d.get("DI"):
            motivos.append("DH sin descripción en DI")
        marca = f"({f['cedula']})"
        if any(marca in a for a in resultado.get("alertas", [])):
            motivos.append("ver alertas")
        novedad = any(d.get(c) for c in ("AH", "AY", "BD", "DH", "CR",
                                          "DK"))
        salida.append({"estado": "OK" if not motivos else
                       "REVISAR: " + "; ".join(motivos),
                       "novedad": novedad})
    return salida


def _escribir_fila_layout(ws, fila, datos, validacion):
    """Escribe una fila de empleado con el formato de la fila modelo (7)
    del layout y pinta como la firma: amarillo las filas con novedad
    revisadas OK, rojo claro las que hay que revisar."""
    from copy import copy
    from openpyxl.styles import PatternFill
    if fila != 7:
        for c in range(1, _col("DW") + 1):
            modelo, celda = ws.cell(7, c), ws.cell(fila, c)
            if modelo.has_style:
                celda.font = copy(modelo.font)
                celda.number_format = modelo.number_format
                celda.alignment = copy(modelo.alignment)
                celda.border = copy(modelo.border)
                celda.protection = copy(modelo.protection)
    for letra, v in datos.items():
        if v in (None, ""):
            continue
        if isinstance(v, datetime.date) and not isinstance(
                v, datetime.datetime):
            v = datetime.datetime(v.year, v.month, v.day)
        ws.cell(fila, _col(letra), v)
    ws.cell(fila, _col("DW"), validacion["estado"])
    color = (ROJO_NE if validacion["estado"] != "OK" else
             AMARILLO_NE if validacion["novedad"] else None)
    relleno = (PatternFill("solid", fgColor=color) if color else
               PatternFill(fill_type=None))
    for c in range(1, _col("DW") + 1):
        ws.cell(fila, c).fill = relleno


def excel_nomina_electronica_subir(resultado, ctx=None):
    """v6.11.1: archivo plano para subir: el layout de carga de la firma
    TAL CUAL (encabezado, colores, letras, anchos) con una fila por
    empleado desde la fila 7, todo en valores (sin formulas ni filas de
    totales). DW = validacion de la fila (OK / REVISAR), pintada como lo
    hace la firma."""
    libro, ws = _libro_layout()
    validacion = validar_filas_ne(resultado)
    for i, (f, v) in enumerate(zip(resultado["filas"], validacion)):
        _escribir_fila_layout(ws, 7 + i, f["fila"], v)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()
