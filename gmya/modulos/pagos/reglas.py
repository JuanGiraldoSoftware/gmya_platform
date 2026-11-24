"""Reglas de armado de la programacion (EMPRESA C): que se paga, en que orden y
con que observaciones.

Contrato:
  armar_prog_pagos(helisa, conceptos, anterior, fecha, fechas_pago, ...)
      -> partidas.
  orden_partidas(partidas) -> orden de la hoja.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.pagos.lectura
"""

import datetime
import re
from collections import defaultdict

from gmya.comun.texto import comparable
from gmya.comun.numeros import formato_cop
from gmya.modulos.pagos.lectura import (
    clave_documento, concepto_documento, correr_meses_texto, fecha_celda_pp,
    MESES_PP, sumar_mes, tiene_mes,
)


# ------------------------------------------------------------
# Reglas para armar la programacion actual
# ------------------------------------------------------------
def _pagado_en(prog, fechas_ant, fecha_actual):
    """Valor programado en fechas de pago que ya pasaron (se da por
    pagado) y valor programado a futuro."""
    pagado = futuro = 0.0
    for valor, fecha in zip(prog, fechas_ant):
        if not valor:
            continue
        if fecha is not None and fecha <= fecha_actual:
            pagado += valor
        else:
            futuro += valor
    return round(pagado, 2), round(futuro, 2)


def _columna_corrida(prog, fechas_ant, fechas_nuevas, fecha_actual):
    """Indice de la nueva fecha de pago para lo que en la anterior estaba
    programado a futuro; None si no estaba programado."""
    for valor, fecha in zip(prog, fechas_ant):
        if not valor or (fecha is not None and fecha <= fecha_actual):
            continue
        if fecha is None:
            return 0
        for i, nueva in enumerate(fechas_nuevas):
            if nueva >= fecha:
                return i
        return len(fechas_nuevas) - 1
    if any(prog):
        return 0           # programado a una fecha ya pasada y sin pagar
    return None


def _columna_por_fecha(fecha, fechas_nuevas):
    if fecha is None:
        return None
    for i, nueva in enumerate(fechas_nuevas):
        if fecha <= nueva:
            return i
    return None


def _proveedores_fijos(anterior):
    """Nombres y cedulas/NIT de los pagos fijos de la anterior: sus
    facturas en HELISA no van en el bloque de facturas."""
    nombres, nits = {}, {}
    for g in anterior["fijos"]:
        nombre = comparable(g["nombre"])
        if len(nombre) >= 4:
            nombres[nombre] = g["nombre"]
        for item in g["items"]:
            for m in re.finditer(r"\d[\d.,]{5,}\d", item["concepto"]):
                nits[re.sub(r"\D", "", m.group(0))] = g["nombre"]
    return nombres, nits


def _grupo_fijo_de(doc, nombres, nits):
    if doc["nit"] in nits:
        return nits[doc["nit"]]
    prov = comparable(doc["proveedor"])
    for nombre, original in nombres.items():
        if prov == nombre or prov.startswith(nombre + " "):
            return original
    return None


def _proyecciones_recurrentes(documentos, fecha, cuentas):
    """Facturas mensuales del mismo valor (honorarios) que llegaron los
    tres meses anteriores y aun no llegan este mes."""
    por_proveedor = defaultdict(list)
    for d in documentos:
        if d["fecha"] and any(d["cuenta"].startswith(c) for c in cuentas):
            por_proveedor[d["nit"]].append(d)
    meses = [sumar_mes(fecha.replace(day=1), -k) for k in (1, 2, 3)]
    salida = []
    for nit, docs in por_proveedor.items():
        de_mes = defaultdict(list)
        for d in docs:
            de_mes[(d["fecha"].year, d["fecha"].month)].append(d)
        if de_mes.get((fecha.year, fecha.month)):
            continue
        ultimos = []
        for m in meses:
            lista = de_mes.get((m.year, m.month))
            if not lista:
                break
            ultimos.append(max(lista, key=lambda x: x["valor"]))
        if len(ultimos) < 3:
            continue
        valores = {round(x["valor"], 2) for x in ultimos}
        if len(valores) != 1:
            continue
        salida.append(ultimos[0])
    return salida


def armar_prog_pagos(helisa, conceptos, anterior, fecha, fechas_pago,
                     empresa=None):
    """
    Lista de partidas de la programacion ACTUAL, cada una con una
    decision sugerida (incluir y fecha de pago) y el motivo. La interfaz
    permite cambiar ambas antes de generar el Excel.
    """
    empresa = empresa or {}
    fechas_ant = anterior["fechas_pago"]
    fecha_ant = anterior["fecha"] or (fecha - datetime.timedelta(days=7))
    partidas = []

    def nueva(**datos):
        datos.setdefault("obs", "")
        datos.setdefault("hijos", [])
        datos.setdefault("fila_ant", None)
        datos.setdefault("fila_helisa", None)
        datos.setdefault("revisar", [])
        datos["id"] = f"P{len(partidas) + 1:03d}"
        partidas.append(datos)
        return datos

    # --- Facturas -------------------------------------------------------
    docs = helisa["documentos"]
    con_saldo = [d for d in docs if d["saldo"] > 0.004]
    por_clave = {clave_documento(d["nit"], d["numero"]): d for d in docs}
    claves_saldo = {clave_documento(d["nit"], d["numero"]) for d in con_saldo}
    ant_por_clave = {clave_documento(f["nit"], f["numero"]): f
                     for f in anterior["facturas"]}
    nombres_fijos, nits_fijos = _proveedores_fijos(anterior)

    for d in con_saldo:
        clave = clave_documento(d["nit"], d["numero"])
        ant = ant_por_clave.get(clave)
        concepto = (ant["concepto"] if ant and ant["concepto"] else
                    concepto_documento(conceptos, d["numero"],
                                       d["proveedor"]))
        abono = round(d["valor"] - d["saldo"], 2)
        if abono > 0.004 and not comparable(concepto).startswith("SALDO"):
            concepto = "SALDO, " + concepto
        grupo_fijo = _grupo_fijo_de(d, nombres_fijos, nits_fijos)
        if grupo_fijo and not ant:
            incluir, programar = False, None
            motivo = (f"Pendiente en HELISA, pero el proveedor se programa "
                      f"en los pagos fijos ({grupo_fijo}).")
            origen = "HELISA · pago fijo"
        elif ant:
            incluir = True
            programar = _columna_corrida(ant["prog"], fechas_ant,
                                         fechas_pago, fecha)
            motivo = "Pendiente en HELISA y en la programación anterior."
            origen = "HELISA"
        else:
            incluir, programar = True, 0
            motivo = "Factura nueva con saldo en HELISA."
            origen = "HELISA · nueva"
        revisar = []
        if ant:
            pagado, _ = _pagado_en(ant["prog"], fechas_ant, fecha)
            if pagado > 0.004:
                revisar.append(
                    "Estaba programada para una fecha de pago que ya pasó y "
                    "HELISA la sigue mostrando con saldo: confirma si se "
                    "pagó (y falta registrar el egreso) o si quedó pendiente.")
        elif incluir and d["fecha"] and anterior.get("fecha") and \
                d["fecha"] < anterior["fecha"]:
            revisar.append(
                f"Factura del {d['fecha']:%d/%m/%Y}, anterior a la "
                f"programación pasada ({anterior['fecha']:%d/%m/%Y}), que "
                "no estaba en ella: confirma que no se dejó por fuera a "
                "propósito (o que llegó tarde a HELISA).")
        if abono > 0.004:
            revisar.append(f"Tiene abonos por {formato_cop(abono)}: se "
                           "programa solo el saldo.")
        if d["vence"] and (fecha - d["vence"]).days > 90:
            revisar.append(f"Vencida hace {(fecha - d['vence']).days} días.")
        nueva(seccion="factura", cuenta=d["cuenta"], nit=d["nit"],
              proveedor=(ant["proveedor"] if ant else d["proveedor"]),
              tipo=d["tipo"], numero=d["numero"], concepto=concepto,
              fecha=d["fecha"], vence=d["vence"], valor=d["valor"],
              abono=abono, saldo=d["saldo"], programar=programar,
              obs=ant["obs"] if ant else "", incluir=incluir, motivo=motivo,
              origen=origen, fila_helisa=d.get("fila"),
              fila_ant=ant["fila"] if ant else None,
              revisar=revisar if incluir else [])

    # Partidas de la anterior que HELISA no muestra con saldo.
    for f in anterior["facturas"]:
        clave = clave_documento(f["nit"], f["numero"])
        if clave in claves_saldo:
            continue
        pagado, futuro = _pagado_en(f["prog"], fechas_ant, fecha)
        en_helisa = clave in por_clave
        if pagado > 0.004 and futuro <= 0.004:
            incluir = False
            motivo = ("Estaba programada para una fecha de pago que ya pasó: "
                      "se da por pagada.")
        elif en_helisa and futuro <= 0.004:
            incluir = False
            motivo = "HELISA la muestra sin saldo: se da por pagada."
        else:
            incluir = True
            motivo = "Sigue pendiente según la programación anterior."
        nueva(seccion="factura", cuenta=f["cuenta"], nit=f["nit"],
              proveedor=f["proveedor"], tipo=f["tipo"], numero=f["numero"],
              concepto=f["concepto"], fecha=f["fecha"], vence=f["vence"],
              valor=f["valor"], abono=f["abono"], saldo=f["saldo"],
              programar=_columna_corrida(f["prog"], fechas_ant, fechas_pago,
                                         fecha) if incluir else None,
              obs=f["obs"], incluir=incluir, motivo=motivo,
              origen="Programación anterior", fila_ant=f["fila"],
              fila_helisa=(por_clave[clave].get("fila")
                           if clave in por_clave else None))

    # Honorarios mensuales que todavia no se han facturado este mes.
    cuentas = empresa.get("cuentas_recurrentes", ("233525",))
    for ultimo in _proyecciones_recurrentes(docs, fecha, cuentas):
        base = concepto_documento(conceptos, ultimo["numero"],
                                  ultimo["proveedor"]) or ""
        mes_txt = MESES_PP[fecha.month - 1]
        if base and tiene_mes(base):
            meses_dif = (fecha.year - ultimo["fecha"].year) * 12 + \
                fecha.month - ultimo["fecha"].month
            concepto = correr_meses_texto(base, meses_dif)
        else:
            concepto = f"HONORARIOS CORRESPONDIENTES AL MES DE {mes_txt} " \
                       f"AÑO {fecha.year}"
        vence = fechas_pago[-1] if fechas_pago else fecha
        ant_prov = next((f["proveedor"] for f in anterior["facturas"]
                         if f["nit"] == ultimo["nit"]), ultimo["proveedor"])
        nueva(seccion="factura", cuenta=ultimo["cuenta"], nit=ultimo["nit"],
              proveedor=ant_prov, tipo=ultimo["tipo"], numero="",
              concepto=concepto, fecha=fecha, vence=vence,
              valor=ultimo["valor"], abono=0.0, saldo=ultimo["valor"],
              programar=_columna_por_fecha(vence, fechas_pago),
              incluir=True, origen="Proyección",
              fila_helisa=ultimo.get("fila"),
              revisar=[f"Base de la proyección de {mes_txt.lower()}: la "
                       "factura del mes aún no llega. Confirma el valor o "
                       "quita la fila si ya no aplica."],
              motivo=(f"Factura mensual del mismo valor los últimos tres "
                      f"meses; la de {mes_txt.lower()} aún no llega a "
                      "HELISA."))

    # --- Anticipos ------------------------------------------------------
    for a in anterior["anticipos"]:
        pagado, futuro = _pagado_en(a["prog"], fechas_ant, fecha)
        incluir = not (pagado > 0.004 and futuro <= 0.004)
        nueva(seccion="anticipo", bloque=a["bloque"], proveedor=a["proveedor"],
              concepto=a["concepto"], fecha=a["fecha"], valor=a["valor"],
              abono=a["abono"], saldo=a["saldo"],
              programar=_columna_corrida(a["prog"], fechas_ant, fechas_pago,
                                         fecha) if incluir else None,
              obs=a["obs"], incluir=incluir, origen="Programación anterior",
              fila_ant=a["fila"],
              motivo=("Se programó en una fecha que ya pasó: se da por "
                      "pagado." if not incluir else
                      "Anticipo pendiente de la programación anterior."))

    # --- Pagos fijos ----------------------------------------------------
    abonos_helisa = {d["nit"]: d for d in con_saldo
                     if d["valor"] - d["saldo"] > 0.004}
    for g in anterior["fijos"]:
        for item in g["items"]:
            pagado, futuro = _pagado_en(item["prog"], fechas_ant, fecha)
            f_item = fecha_celda_pp(item["fecha"])
            en_ventana = f_item is not None and fecha_ant < f_item <= fecha
            parcial = 0.004 < pagado < item["saldo"] - 0.5
            corre = pagado > 0.004 or en_ventana
            hijos = [h for h in item["hijos"]
                     if not comparable(h["concepto"]).startswith("LIQUIDACION")]
            if comparable(item["concepto"]).startswith("SALDO") and \
                    pagado > 0.004 and pagado >= item["saldo"] - 0.5:
                # Saldo de un mes anterior que ya se pago: no se repite.
                nueva(seccion="fijo", bloque=g["bloque"], grupo=g["nombre"],
                      concepto=item["concepto"], fecha=item["fecha"],
                      valor=item["valor"], abono=item["abono"],
                      saldo=item["saldo"], programar=None, obs=item["obs"],
                      incluir=False, origen="Pago fijo · saldo",
                      fila_ant=item["fila"],
                      motivo=("Saldo programado en una fecha que ya pasó: "
                              "se da por pagado."))
                continue
            if corre:
                nueva_fecha = sumar_mes(f_item) if f_item else item["fecha"]
                h_nuevos = [dict(h, concepto=correr_meses_texto(h["concepto"]),
                                 fecha=(sumar_mes(fecha_celda_pp(h["fecha"]))
                                        if fecha_celda_pp(h["fecha"])
                                        else h["fecha"]))
                            for h in hijos]
                valor = round(sum(h["valor"] for h in h_nuevos), 2) \
                    if h_nuevos else item["valor"]
                nueva(seccion="fijo", bloque=g["bloque"], grupo=g["nombre"],
                      concepto=correr_meses_texto(item["concepto"]),
                      fecha=nueva_fecha, valor=valor, abono=0.0, saldo=valor,
                      programar=_columna_por_fecha(
                          fecha_celda_pp(nueva_fecha), fechas_pago),
                      hijos=h_nuevos, obs=item["obs"], incluir=True,
                      origen="Pago fijo · siguiente mes", fila_ant=item["fila"],
                      revisar=([] if pagado > 0.004 else [
                          "Pasa al mes siguiente porque su fecha ya pasó, "
                          "aunque en la anterior no figuraba como pagado ("
                          + ("estaba programado para una fecha posterior"
                             if futuro > 0.004 else "no tenía fecha de pago")
                          + "). Confirma que el pago del mes sí se hizo."]),
                      motivo=("Pagado en la programación anterior: pasa al "
                              "mes siguiente." if pagado > 0.004 else
                              "Su fecha ya pasó: pasa al mes siguiente."))
                if parcial:
                    nits = [re.sub(r"\D", "", m.group(0)) for m in
                            re.finditer(r"\d[\d.,]{5,}\d", item["concepto"])]
                    doc = next((abonos_helisa[n] for n in nits
                                if n in abonos_helisa), None)
                    abono = round(doc["valor"] - doc["saldo"], 2) if doc \
                        else pagado
                    concepto = item["concepto"]
                    if not comparable(concepto).startswith("SALDO"):
                        concepto = "SALDO, " + concepto
                    nueva(seccion="fijo", bloque=g["bloque"],
                          grupo=g["nombre"], concepto=concepto,
                          fecha=item["fecha"], valor=item["valor"],
                          abono=abono,
                          saldo=round(item["valor"] - abono, 2),
                          programar=0, obs=item["obs"], incluir=True,
                          origen="Pago fijo · saldo", fila_ant=item["fila"],
                          revisar=[f"Pago parcial: se abonó "
                                   f"{formato_cop(abono)} y queda el saldo. "
                                   "Confirma el abono."],
                          motivo=("Se pagó solo una parte: queda el saldo "
                                  + ("(abono tomado de HELISA)." if doc else
                                     "(abono = valor programado en la "
                                     "fecha que ya pasó).")))
                continue
            valor = round(sum(h["valor"] for h in hijos), 2) \
                if hijos else item["valor"]
            col = _columna_corrida(item["prog"], fechas_ant, fechas_pago,
                                   fecha)
            if col is None and f_item and fecha < f_item:
                col = _columna_por_fecha(f_item, fechas_pago)
            nueva(seccion="fijo", bloque=g["bloque"], grupo=g["nombre"],
                  concepto=item["concepto"], fecha=item["fecha"], valor=valor,
                  abono=item["abono"], saldo=round(valor - item["abono"], 2),
                  programar=col, hijos=hijos, obs=item["obs"], incluir=True,
                  origen="Pago fijo", fila_ant=item["fila"],
                  revisar=([f"Su fecha ({f_item:%d/%m/%Y}) ya pasó y no se ha "
                            "programado: confirma si sigue pendiente."]
                           if f_item and f_item < fecha_ant else []),
                  motivo="Pago fijo pendiente: se mantiene.")
    return partidas


def orden_partidas(partidas):
    """Facturas por proveedor (como HELISA), luego anticipos y pagos fijos
    en el orden de la anterior."""
    facturas = [p for p in partidas if p["seccion"] == "factura"]
    facturas.sort(key=lambda p: (comparable(p["proveedor"]),
                                 0 if p["numero"] else 1,
                                 comparable(p["numero"])))
    return (facturas + [p for p in partidas if p["seccion"] == "anticipo"]
            + [p for p in partidas if p["seccion"] == "fijo"])
