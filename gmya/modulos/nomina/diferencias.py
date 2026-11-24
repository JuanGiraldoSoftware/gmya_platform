"""Datos del panel de diferencias de nomina (v6.14, sin Streamlit).
Modelo: gmya/ui/visual.py (panel de diferencias).

Contrato:
  panel_nomina_banco(cruce, planillas, valores) -> [concepto]
      A = total del Excel del banco DESPUES de actualizar, B = total de las
      planillas. Composicion (suma EXACTA A - B): filas no actualizadas,
      cedulas repetidas, empleados del Excel sin planilla (conservan su
      valor), empleados de la planilla que no estan en el Excel (no se
      agregan: solo alerta) y diferencia de lectura del total de la
      planilla. Partidas: cada empleado con algo de eso.
  panel_conciliacion_nomina(resultado) -> [concepto] (uno por grupo):
      devengos y descuentos: HELISA (pagado) vs contabilidad (o
      liquidacion); prestaciones: liquidacion vs contabilidad (provision).
      Composicion: un renglon por concepto que no cuadra. Partidas: cada
      empleado y concepto que no cuadra, con los tres valores.
  panel_controles_ne(resultado) -> [concepto]: A = plantilla de nomina
      electronica, B = contabilidad / acumulado; una fila por columna con
      diferencia.
Depende de: gmya.comun.numeros, gmya.modulos.nomina.conciliacion
"""

from gmya.comun.numeros import formato_cop
from gmya.modulos.nomina.conciliacion import GRUPOS


def _f(v):
    return round(float(v or 0), 2)


def _c(etiqueta, valor, n=None, tipo="pendiente"):
    return {"etiqueta": etiqueta, "valor": _f(valor), "tipo": tipo, "n": n}


# ------------------------------------------------------------
# Pago de nomina en el formato del banco
# ------------------------------------------------------------
def panel_nomina_banco(cruce, planillas, valores):
    filas = cruce["filas"]
    final = {f["fila"]: _f(valores.get(f["fila"], f["valor"])) for f in filas}
    total_a = _f(sum(final.values()))
    total_b = _f(sum(p["total"] for p in planillas))
    suma_emp = _f(sum(e["valor"] for p in planillas for e in p["empleados"]))
    comp, partidas = [], []

    def partida(f, causa, nota, a, b):
        partidas.append({
            "id": f"F{f.get('fila', '')}{f['cedula']}",
            "titulo": f["nombre"] or f["cedula"],
            "sub": f"C.C. {f['cedula']}" + (f" · fila {f['fila']} del Excel"
                                            if f.get("fila") else ""),
            "causa": causa, "tipo": "valor" if a is not None and b is not None
            else ("solo_a" if b is None else "solo_b"),
            "a": a, "b": b, "nota": nota,
            "lado_a": "Excel", "lado_b": "Planilla",
            "detalle": [("Nombre", f["nombre"], f.get("nombre_planilla") or "—",
                         bool(f.get("nombre_planilla")) and
                         f.get("estado") == "nombre"),
                        ("Valor", a if a is not None else "—",
                         b if b is not None else "—")]})

    # Filas con planilla que no se actualizan (desmarcadas o nombre).
    no_act = [f for f in filas if f["valor_nuevo"] is not None
              and f["estado"] != "repetido" and f["fila"] not in valores]
    if no_act:
        comp.append(_c("Filas que no se actualizan (desmarcadas o nombre "
                       "por confirmar)", sum(final[f["fila"]] - f["valor_nuevo"]
                                             for f in no_act), len(no_act)))
        for f in no_act:
            if abs(final[f["fila"]] - f["valor_nuevo"]) >= 0.005 or \
                    f["estado"] == "nombre":
                partida(f, "Nombre distinto" if f["estado"] == "nombre"
                        else "No se actualiza",
                        "La cédula coincide pero el nombre no: confirma y "
                        "marca Actualizar." if f["estado"] == "nombre" else
                        "Está desmarcada en la revisión: conserva el valor "
                        "actual del Excel.", final[f["fila"]],
                        _f(f["valor_nuevo"]))
    # Cedulas repetidas en el Excel.
    rep = {}
    for f in filas:
        if f["estado"] == "repetido":
            rep.setdefault(f["cedula"], []).append(f)
    if rep:
        comp.append(_c("Cédulas repetidas en el Excel (no se actualizan)",
                       sum(sum(final[f["fila"]] for f in fs) -
                           _f(fs[0]["valor_nuevo"]) for fs in rep.values()),
                       len(rep)))
        for fs in rep.values():
            partida(dict(fs[0], fila=", ".join(str(f["fila"]) for f in fs)),
                    "Cédula repetida", "La misma cédula está en varias filas "
                    "del Excel: no se actualiza; corrígelo en el formato del "
                    "banco.", _f(sum(final[f["fila"]] for f in fs)),
                    _f(fs[0]["valor_nuevo"]))
    sin = [f for f in filas if f["estado"] == "sin_planilla"]
    if sin:
        comp.append(_c("En el Excel sin planilla (conservan su valor)",
                       sum(final[f["fila"]] for f in sin), len(sin)))
        for f in sin:
            partida(f, "No está en las planillas", "No se borra (regla del "
                    "formato del banco): revisa si debe salir o quedar en "
                    "cero.", final[f["fila"]], None)
    solo = cruce.get("solo_planilla") or []
    if solo:
        comp.append(_c("En la planilla y no en el Excel (no se agregan)",
                       -sum(d["valor"] for d in solo), len(solo)))
        for d in solo:
            partida(dict(d, fila=None), "No está en el Excel",
                    "No se agrega (regla del formato del banco): si debe "
                    "pagarse, inclúyelo tú en el formato." +
                    (f" Nombre parecido con otra cédula: "
                     f"{d['parecido']['nombre']} (C.C. "
                     f"{d['parecido']['cedula']})." if d.get("parecido")
                     else ""), None, _f(d["valor"]))
    if abs(suma_emp - total_b) >= 0.005:
        comp.append(_c("Total de la planilla distinto de la suma de sus "
                       "empleados (lectura del PDF)", suma_emp - total_b))
    ok = sum(1 for f in filas if f["fila"] in valores)
    return [{
        "clave": "Pago de nómina", "nombre": "",
        "sub": f"{len(filas)} filas en el Excel · {len(planillas)} "
               f"planilla{'s' if len(planillas) != 1 else ''}",
        "lado_a": "Excel", "lado_b": "Planillas",
        "total_a": total_a, "total_b": total_b,
        "dona": [("Se actualizan", ok, "ok"),
                 ("No se actualizan", len(no_act) + sum(
                     len(x) for x in rep.values()), "alerta"),
                 ("Sin planilla", len(sin), "error")],
        "centro": str(len(filas)), "centro_sub": "filas del Excel",
        "datos": [("Total del Excel después", formato_cop(total_a)),
                  ("Total planillas", formato_cop(total_b)),
                  ("Diferencia", formato_cop(total_a - total_b)),
                  ("Solo en la planilla", str(len(solo)))],
        "composicion": [x for x in comp if abs(x["valor"]) >= 0.005],
        "partidas": partidas, "grupos": [],
        "pie_comp": "Queda por revisar antes de generar el archivo",
    }]


# ------------------------------------------------------------
# Conciliacion de nomina (HELISA / liquidacion / contabilidad)
# ------------------------------------------------------------
def _lados(grupo, tiene_l, tiene_b):
    if grupo == "prestacion":
        return ("liquidacion", "Liquidación"), ("contabilidad", "Contabilidad")
    if grupo != "descuento" and tiene_b:
        return ("acumulado", "HELISA"), ("contabilidad", "Contabilidad")
    if tiene_l:
        return ("acumulado", "HELISA"), ("liquidacion", "Liquidación")
    return None


def panel_conciliacion_nomina(resultado):
    tl, tb = resultado["tiene_liquidacion"], resultado["tiene_balance"]
    salida = []
    for grupo, nombre in GRUPOS.items():
        lados = _lados(grupo, tl, tb)
        res = [r for r in resultado["resumen"] if r["grupo"] == grupo]
        if not lados or not res:
            continue
        (ka, la), (kb, lb) = lados
        total_a = _f(sum(r[ka] or 0 for r in res))
        total_b = _f(sum(r[kb] or 0 for r in res))
        comp = [_c(r["nombre"], (r[ka] or 0) - (r[kb] or 0))
                for r in res if abs((r[ka] or 0) - (r[kb] or 0)) >= 0.005]
        malas = [f for f in resultado["filas"] if f["grupo"] == grupo
                 and f["estado"] in ("NO CUADRA", "DIFERENCIA DE CENTAVOS")]
        partidas = []
        for f in malas:
            det = [("HELISA (pagado)", _f(f["acumulado"]) if f["acumulado"]
                    is not None else "—", "")]
            if tl:
                det.append(("Liquidación", _f(f["liquidacion"]) if
                            f["liquidacion"] is not None else "—", ""))
            if tb and grupo != "descuento":
                det.append(("Contabilidad", _f(f["contabilidad"]) if
                            f["contabilidad"] is not None else "—", ""))
            a, b = f[ka], f[kb]
            partidas.append({
                "id": f"{f['cedula']}-{f['concepto']}",
                "titulo": f["nombre"] or f["cedula"],
                "sub": f"C.C. {f['cedula']} · {f['nombre_concepto']}",
                "causa": f["nombre_concepto"],
                "tipo": "valor", "a": None if a is None else _f(a),
                "b": None if b is None else _f(b),
                "nota": ("Diferencia de centavos: revisar el redondeo en el "
                         "documento de origen (no se ajusta)." if f["estado"]
                         == "DIFERENCIA DE CENTAVOS" else
                         "Los valores no cuadran entre los documentos."),
                "lado_a": la, "lado_b": lb, "detalle_simple": True,
                "detalle": det})
        estados = [r["estado"] for r in res]
        salida.append({
            "clave": nombre.split(" (")[0], "nombre": "",
            "sub": f"{la} vs {lb} · {len(res)} conceptos",
            "lado_a": la, "lado_b": lb, "total_a": total_a,
            "total_b": total_b,
            "dona": [("Cuadran", estados.count("CUADRA"), "ok"),
                     ("Centavos", estados.count("DIFERENCIA DE CENTAVOS"),
                      "alerta"),
                     ("No cuadran", estados.count("NO CUADRA"), "error")],
            "centro": str(len(res)), "centro_sub": "conceptos",
            "datos": [(f"Total {la}", formato_cop(total_a)),
                      (f"Total {lb}", formato_cop(total_b)),
                      ("Diferencia", formato_cop(total_a - total_b)),
                      ("Empleado-concepto por revisar", str(len(malas)))],
            "composicion": comp, "partidas": partidas, "grupos": []})
    return salida


# ------------------------------------------------------------
# Nomina electronica: controles de la plantilla
# ------------------------------------------------------------
def panel_controles_ne(resultado):
    ctl = resultado["controles"]
    if not ctl:
        return []
    total_a = _f(sum(c["plantilla"] for c in ctl))
    total_b = _f(sum(c["fuente"] for c in ctl))
    malos = [c for c in ctl if abs(c["diferencia"]) >= 0.005]
    return [{
        "clave": "Controles", "nombre": "",
        "sub": f"{len(resultado['filas'])} empleados · {len(ctl)} columnas "
               "controladas",
        "lado_a": "Plantilla", "lado_b": "Fuente",
        "total_a": total_a, "total_b": total_b,
        "dona": [("Cuadran", len(ctl) - len(malos), "ok"),
                 ("Con diferencia", len(malos), "error")],
        "centro": str(len(ctl)), "centro_sub": "columnas",
        "datos": [("Columnas que cuadran", f"{len(ctl) - len(malos)} de "
                                           f"{len(ctl)}"),
                  ("Alertas", str(len(resultado.get("alertas") or []))),
                  ("Empleados", str(len(resultado["filas"]))),
                  ("Diferencia total", formato_cop(total_a - total_b))],
        "composicion": [_c(f"{c['concepto']} (columna {c['columna']})",
                           c["diferencia"]) for c in malos],
        "partidas": [{
            "id": c["columna"], "titulo": f"{c['concepto']} · columna "
                                          f"{c['columna']}",
            "sub": f"Plantilla vs {c['origen'].lower()}",
            "causa": c["origen"], "tipo": "valor",
            "a": _f(c["plantilla"]), "b": _f(c["fuente"]),
            "nota": "El total de la columna de la plantilla no coincide con "
                    "la fuente: revisa los empleados con novedad en ese "
                    "concepto (no se ajusta).",
            "lado_a": "Plantilla", "lado_b": c["origen"],
            "detalle": [("Total", _f(c["plantilla"]), _f(c["fuente"]))]}
            for c in malos],
        "grupos": [],
    }]
