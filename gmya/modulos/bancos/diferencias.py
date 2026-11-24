"""Datos del panel de diferencias de la conciliacion bancaria (v6.14, sin
Streamlit). Una pestana por cuenta. Modelo: gmya/ui/visual.py.

Contrato:
  panel_diferencias_bancos(resultado) -> [concepto] (uno por cuenta):
    total_a = saldo final HELISA, total_b = saldo final extracto.
    composicion (suma EXACTA total_a - total_b, identidad de conciliacion):
      explicada: partidas de HELISA en transito (cheques / egresos o
        consignaciones registrados al cierre que el banco aun no muestra);
      pendiente: gastos bancarios e intereses del extracto sin registrar,
        otros movimientos del extracto sin registrar, otros registros de
        HELISA sin extracto, valores diferentes, diferencia de saldos
        iniciales y lo no explicado.
    partidas: cada movimiento pendiente con la causa probable (motor de
      sugerencias) y su accion.
Depende de: gmya.comun.numeros
"""

from gmya.comun.numeros import formato_cop

TRANSITO = ("TRÁNSITO", "TRANSITO")
BANCARIAS = ("gmf", "comision", "iva_bancario", "rendimientos")
ESTADO_TXT = {"sin_libro": "No está en HELISA",
              "sin_extracto": "No está en el extracto",
              "diferencia": "Valor diferente",
              "agrupado_diferencia": "Valor diferente (agrupado)"}


def _f(v):
    return round(float(v or 0), 2)


def _sugerencia(m, por_id):
    for ident in m.get("sugerencias") or []:
        if ident in por_id:
            return por_id[ident]
    return None


def _desc_libro(m):
    return " ".join(str(x) for x in (m.get("tipo"), m.get("numero"),
                                     m.get("tercero")) if x).strip()


def _cuenta(c):
    a = c["analisis"]
    conc = a["conc"]
    movs, lib = a["movs"], a["libro_movs"]
    por_id = {s["id"]: s for s in a.get("sugerencias") or []}
    total_a, total_b = _f(conc["saldo_fin_lib"]), _f(conc["saldo_fin_ext"])
    comp, partidas = [], []

    def agregar(etiqueta, valor, tipo, n=None):
        if abs(valor) >= 0.005:
            comp.append({"etiqueta": etiqueta, "valor": _f(valor),
                         "tipo": tipo, "n": n})

    # HELISA sin extracto: en transito (explicada) vs otros (pendiente).
    transito, otros_l = [], []
    for m in lib:
        if m["estado"] != "sin_extracto":
            continue
        s = _sugerencia(m, por_id)
        (transito if s and any(t in s["tipo"].upper() for t in TRANSITO)
         else otros_l).append(m)
    agregar("Partidas de HELISA en tránsito (el banco aún no las muestra)",
            sum(m["valor"] for m in transito), "explicada", len(transito))
    agregar("Otros registros de HELISA que no están en el extracto",
            sum(m["valor"] for m in otros_l), "pendiente", len(otros_l))
    # Extracto sin HELISA (resta): gastos bancarios / intereses vs otros.
    ban = [m for m in movs if m["estado"] == "sin_libro"
           and m.get("categoria") in BANCARIAS]
    otros_e = [m for m in movs if m["estado"] == "sin_libro"
               and m.get("categoria") not in BANCARIAS]
    agregar("Gastos bancarios e intereses del extracto sin registrar",
            -sum(m["valor"] for m in ban), "pendiente", len(ban))
    agregar("Otros movimientos del extracto sin registrar en HELISA",
            -sum(m["valor"] for m in otros_e), "pendiente", len(otros_e))
    dif = [m for m in movs if m["estado"] in ("diferencia",
                                              "agrupado_diferencia")]
    agregar("Valores diferentes entre HELISA y el extracto",
            conc["diferencia_valores"], "pendiente", len(dif))
    agregar("Diferencia en los saldos iniciales (viene del mes anterior)",
            conc["diferencia_saldo_inicial"], "pendiente")
    agregar("Sin explicar", conc["no_explicada"], "pendiente")

    # Gastos bancarios / intereses sin registrar: una partida por categoria
    # (32 cargos de GMF no se revisan uno a uno; se registra una nota).
    por_cat = {}
    for m in ban:
        por_cat.setdefault(m.get("categoria"), []).append(m)
    for cat, ms in por_cat.items():
        s = _sugerencia(ms[0], por_id)
        total = _f(sum(m["valor"] for m in ms))
        nombre = ms[0].get("categoria_nombre") or cat
        partidas.append({
            "id": f"B-{cat}", "titulo": f"{nombre} ({len(ms)} cargo"
                                        f"{'s' if len(ms) != 1 else ''})",
            "sub": f"Extracto · {min(m['fecha'] for m in ms):%d/%m/%Y} a "
                   f"{max(m['fecha'] for m in ms):%d/%m/%Y}",
            "causa": "Nota bancaria pendiente", "tipo": "solo_b",
            "a": None, "b": total,
            "nota": (s["explicacion"] + (" " + s["accion"] if s.get("accion")
                                          else "")) if s else
                    "Cargos del extracto sin registro en HELISA: registrar "
                    "la nota bancaria del periodo.",
            "lado_a": "HELISA", "lado_b": "Extracto",
            "detalle": [("Cargos", "—", str(len(ms))),
                        ("Valor", "—", total)]})
    ids_ban = {id(m) for m in ban}

    for m in movs:
        if m["estado"] not in ESTADO_TXT or id(m) in ids_ban:
            continue
        s = _sugerencia(m, por_id)
        pareja = [lib[i] for i in m.get("pareja") or [] if i < len(lib)]
        a_val = _f(sum(x["valor"] for x in pareja)) if pareja else None
        partidas.append({
            "id": f"E{movs.index(m)}", "titulo": (m.get("descripcion") or
                                                 "Movimiento del extracto")[:70],
            "sub": f"Extracto · {m['fecha']:%d/%m/%Y} · {m.get('ubicacion', '')}"
                   f" · {m.get('categoria_nombre', '')}",
            "causa": (s["tipo"].capitalize() if s else ESTADO_TXT[m["estado"]]),
            "tipo": "valor" if pareja else "solo_b",
            "a": a_val, "b": _f(m["valor"]),
            "nota": (s["explicacion"] + (" " + s["accion"] if s.get("accion")
                                          else "")) if s else m.get("nota", ""),
            "lado_a": "HELISA", "lado_b": "Extracto",
            "detalle": [("Fecha", f"{pareja[0]['fecha']:%d/%m/%Y}" if pareja
                         else "—", f"{m['fecha']:%d/%m/%Y}"),
                        ("Movimiento", "; ".join(_desc_libro(x) for x in pareja)
                         or "—", m.get("descripcion") or ""),
                        ("Valor", a_val, _f(m["valor"]))]})
    ids_tr = {id(m) for m in transito}
    for m in lib:
        if m["estado"] != "sin_extracto" or id(m) in ids_tr:
            continue        # el transito va en su grupo (explicado)
        s = _sugerencia(m, por_id)
        partidas.append({
            "id": f"L{lib.index(m)}", "titulo": _desc_libro(m) or "Registro "
            "de HELISA", "sub": f"HELISA · {m['fecha']:%d/%m/%Y} · "
                                f"{m.get('ubicacion', '')}",
            "causa": s["tipo"].capitalize() if s else ESTADO_TXT[m["estado"]],
            "tipo": "solo_a", "a": _f(m["valor"]), "b": None,
            "nota": (s["explicacion"] + (" " + s["accion"] if s.get("accion")
                                          else "")) if s else "",
            "lado_a": "HELISA", "lado_b": "Extracto",
            "detalle": [("Fecha", f"{m['fecha']:%d/%m/%Y}", "—"),
                        ("Valor", _f(m["valor"]), "—")]})

    estados = {}
    for m in movs:
        estados[m["estado"]] = estados.get(m["estado"], 0) + 1
    ok = estados.get("conciliado", 0) + estados.get("agrupado", 0)
    rev = estados.get("diferencia", 0) + estados.get("agrupado_diferencia", 0)
    sin = estados.get("sin_libro", 0)
    grupos = []
    if transito:
        grupos.append({"etiqueta": "Partidas en tránsito", "n": len(transito),
                       "valor": _f(sum(m["valor"] for m in transito)),
                       "tipo": "explicada",
                       "nota": "Registradas en HELISA al cierre; deben "
                               "aparecer en el extracto del mes siguiente: " +
                               "; ".join(f"{_desc_libro(m)} "
                                         f"{formato_cop(m['valor'])}"
                                         for m in transito[:8]) +
                               (" …" if len(transito) > 8 else "")})
    return {
        "clave": c["etiqueta"], "nombre": "",
        "sub": f"{c.get('archivo_extracto') or 'Sin extracto'} · "
               f"{len(movs)} movimientos del extracto",
        "lado_a": "HELISA", "lado_b": "Extracto",
        "total_a": total_a, "total_b": total_b,
        "dona": [("Conciliados", ok, "ok"), ("Valor diferente", rev, "alerta"),
                 ("No están en HELISA", sin, "error")],
        "centro": str(len(movs)), "centro_sub": "movimientos del extracto",
        "datos": [("Saldo final extracto", formato_cop(conc["saldo_fin_ext"])),
                  ("Saldo final HELISA", formato_cop(conc["saldo_fin_lib"])),
                  ("Por revisar", formato_cop(sum(
                      x["valor"] for x in comp if x["tipo"] == "pendiente"))),
                  ("De HELISA sin extracto", str(len(transito) + len(otros_l)))],
        "composicion": comp, "partidas": partidas, "grupos": grupos,
    }


def panel_diferencias_bancos(resultado):
    return [_cuenta(c) for c in resultado.get("cuentas") or []]



# ------------------------------------------------------------
# v6.16 · Graficos del detalle de cuenta
# ------------------------------------------------------------
TARIFA_IVA = 0.19          # IVA general (art. 468 E.T.) sobre comisiones
ORDEN_GASTOS = ["GMF 4x1000", "Comisión", "IVA sobre comisión",
                "Retención en la fuente", "Intereses ganados"]


def graficos_cuenta(c):
    """Datos para los graficos de una cuenta:
      puente: [(etiqueta, valor, tipo)] saldo final extracto -> ajustes de
        la identidad de conciliacion -> saldo final HELISA (cuadra exacto).
      gastos: [(categoria, cobrado por el banco, registrado en HELISA)] con
        valores positivos (gasto o ingreso, en valor absoluto).
      iva: {"base", "esperado", "cobrado", "diferencia"} control de
        razonabilidad del IVA sobre comisiones gravadas (sin cuota de
        manejo de tarjeta debito, como en el Excel), o None.
    """
    from gmya.modulos.bancos.conciliacion import categoria_gasto
    a = c["analisis"]
    conc = a["conc"]
    pasos = [("Saldo final del extracto", _f(conc["saldo_fin_ext"]), "total")]
    for etiqueta, v in (
            ("Registros de HELISA que no están en el extracto",
             conc["lib_sin_ext"]),
            ("Movimientos del extracto sin registrar en HELISA",
             -_f(conc["ext_sin_lib"])),
            ("Valores diferentes", conc["diferencia_valores"]),
            ("Diferencia de saldos iniciales", conc["diferencia_saldo_inicial"]),
            ("Sin explicar", conc["no_explicada"])):
        if abs(_f(v)) >= 0.005:
            pasos.append((etiqueta, _f(v), "ajuste"))
    pasos.append(("Saldo final de HELISA", _f(conc["saldo_fin_lib"]), "total"))

    cobrado, registrado = {}, {}
    base = 0.0
    for m in a["movs"]:
        cat = categoria_gasto(m)
        if not cat:
            continue
        v = abs(_f(m["valor"]))
        cobrado[cat[0]] = cobrado.get(cat[0], 0) + v
        if m["estado"] in ("conciliado", "agrupado", "diferencia",
                           "agrupado_diferencia"):
            registrado[cat[0]] = registrado.get(cat[0], 0) + v
        if cat[0] == "Comisión" and cat[1] != "Cuota manejo tarjeta débito":
            base += v
    gastos = [(k, round(cobrado[k], 2), round(registrado.get(k, 0), 2))
              for k in ORDEN_GASTOS if k in cobrado]
    iva = None
    if "Comisión" in cobrado or "IVA sobre comisión" in cobrado:
        esperado = round(base * TARIFA_IVA, 2)
        cob = round(cobrado.get("IVA sobre comisión", 0), 2)
        iva = {"base": round(base, 2), "esperado": esperado, "cobrado": cob,
               "diferencia": round(cob - esperado, 2)}
    return {"puente": pasos, "gastos": gastos, "iva": iva}
