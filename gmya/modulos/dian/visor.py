"""Tablas y marcas de diferencias para el visor de la conciliacion DIAN.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.ui.visor, gmya.modulos.dian.parametros, gmya.modulos.dian.acuses
"""

import html
from collections import OrderedDict

from gmya.comun.texto import comparable, solo_nit
from gmya.comun.numeros import numero
from gmya.ui.visor import PALETA_COTEJOS
from gmya.modulos.dian.parametros import (
    dato, dentro_de, TOLERANCIA_IVA_DOCUMENTO,
)
from gmya.modulos.dian.acuses import explicar_acuse_faltante


# ------------------------------------------------------------
# Visor de diferencias de la conciliacion DIAN: muestra el reporte DIAN y
# el informe de HELISA como hojas de calculo (con el numero de fila del
# archivo original), marca cada diferencia con su numero y color en los
# dos documentos y, al pasar el mouse, explica la diferencia.
# ------------------------------------------------------------
def _fila_grilla_a_lista(fila):
    maximo = max([c["col"] for c in fila["celdas"]] or [0])
    valores = [None] * maximo
    for celda in fila["celdas"]:
        valores[celda["col"] - 1] = celda["valor"]
    return valores


def tabla_reporte_dian(reporte):
    """
    (tabla, numero): tabla[n - 1] es la fila n del archivo DIAN y
    numero[id(registro)] la fila de cada documento.
    """
    filas = reporte.get("fila_excel") or {}
    registros = reporte["registros"]
    if registros and all(id(r) in filas for r in registros):
        encabezado = min(filas[id(r)] for r in registros) - 1
        maximo = max(filas[id(r)] for r in registros)
        tabla = [[] for _ in range(maximo)]
        tabla[encabezado - 1] = list(reporte["encabezados"])
        for r in registros:
            tabla[filas[id(r)] - 1] = list(r)
        return tabla, {id(r): filas[id(r)] for r in registros}
    tabla = [list(reporte["encabezados"])] + [list(r) for r in registros]
    return tabla, {id(r): i + 2 for i, r in enumerate(registros)}


def tabla_informe_helisa(informe):
    """(tabla, numero) del informe HELISA tal como se exporto."""
    grilla = informe.get("grilla") or []
    tabla = [_fila_grilla_a_lista(f) for f in grilla]
    return tabla, {id(f): i + 1 for i, f in enumerate(grilla)}


def _cop_dian(valor):
    try:
        return f"${float(valor or 0):,.2f}"
    except (TypeError, ValueError):
        return str(valor)


def _describir_dian(reporte, factura, lado):
    e = html.escape
    prefijo = dato(reporte, factura, "Prefijo") or ""
    folio = dato(reporte, factura, "Folio") or ""
    nombre = dato(reporte, factura, f"Nombre {lado}") or ""
    nit = solo_nit(dato(reporte, factura, f"NIT {lado}"))
    fecha = dato(reporte, factura, "Fecha Emisión") or ""
    return (f"{e(str(prefijo))}{e(str(folio))} · {e(str(fecha))} · "
            f"{e(str(nombre))[:45]} (NIT {e(nit)}) · total "
            f"{_cop_dian(dato(reporte, factura, 'Total'))} · IVA "
            f"{_cop_dian(dato(reporte, factura, 'IVA'))}")


def _describir_helisa(doc):
    e = html.escape
    return (f"{e(doc['documento'])} · {e(doc.get('fecha') or '')} · "
            f"{e(doc.get('beneficiario') or '')[:45]} (NIT "
            f"{e(doc.get('nit') or '')}) · total "
            f"{_cop_dian(doc['total_debito'])} · IVA "
            f"{_cop_dian(doc.get('iva'))}")


def diferencias_dian(analisis):
    """
    {clave_concepto: [diferencia]}. Cada diferencia: numero, etiqueta,
    color, estado, filas del reporte DIAN ('dian'), filas del informe
    HELISA ('helisa') y la explicacion en HTML ('texto').
    """
    reporte = analisis["reporte"]
    tolerancia = float(analisis["parametros"].get("tolerancia_redondeo",
                                                  0))
    salida = OrderedDict()
    for r in analisis["resultados"]:
        concepto = r["concepto"]
        clave = concepto["clave"]
        lado = "Receptor" if comparable(concepto["grupo"]) == "EMITIDO" \
            else "Emisor"
        items = []

        def agregar(estado, dian, helisa, texto, que_hacer, orden=1):
            items.append({"estado": estado, "dian": dian, "helisa": helisa,
                          "texto": texto, "que_hacer": que_hacer,
                          "orden": orden})

        if r["modo"] == "detalle":
            docs = r["documentos_helisa"] or []
            for j, factura in enumerate(r["dian"]):
                if j not in r["dian_a_helisa"]:
                    agregar("NO ESTÁ EN HELISA", [factura], [],
                            f"Está en el reporte DIAN y no se encontró en "
                            f"HELISA: {_describir_dian(reporte, factura, lado)}.",
                            "Contabilizarlo en HELISA o verificar si se "
                            "registró con otro número, otro NIT o en otro "
                            "periodo.", 0)
            for doc in docs:
                filas_h = [m["fila"] for m in doc["movimientos"]]
                if doc.get("fila_total"):
                    filas_h.append(doc["fila_total"])
                factura = r["dian"][doc["dian"]] if doc.get("dian") is not \
                    None else None
                dian = [factura] if factura is not None else []
                if doc["estado"] == "no_dian" and doc.get("otro_concepto"):
                    agregar("DE OTRO CONCEPTO", [], filas_h,
                            f"Está en este informe de HELISA pero es de otro "
                            f"concepto ({html.escape(doc['otro_concepto'])}): "
                            f"{_describir_helisa(doc)}.",
                            "Se resta aquí como NO DIAN porque el reporte "
                            "DIAN lo trae en el otro concepto. Verificar que "
                            "esté bien clasificado en HELISA.", 1)
                elif doc["estado"] == "no_dian":
                    agregar("NO ESTÁ EN LA DIAN", [], filas_h,
                            f"Está en HELISA y no aparece en el reporte DIAN: "
                            f"{_describir_helisa(doc)}.",
                            "Verificar si es un documento electrónico, si "
                            "el tercero ya lo transmitió o si es de otro "
                            "periodo. Si es un soporte no electrónico, "
                            "queda como NO DIAN.", 0)
                elif doc["estado"] == "diferencia":
                    agregar("VALOR DIFERENTE", dian, filas_h,
                            f"HELISA: {_describir_helisa(doc)}.<br>DIAN: "
                            f"{_describir_dian(reporte, factura, lado)}."
                            f"<br>Diferencia (HELISA − DIAN): "
                            f"<b>{_cop_dian(doc['diferencia'])}</b>, mayor "
                            f"que la tolerancia de redondeo "
                            f"({_cop_dian(tolerancia)}).",
                            "Revisar el comprobante: puede haber impuestos "
                            "asumidos, retenciones o un valor mal "
                            "digitado.", 1)
                elif doc.get("nivel") == 4:
                    agregar("FOLIO DISTINTO", dian, filas_h,
                            f"Se cruzó por NIT y valor, pero el número no "
                            f"coincide.<br>HELISA: {_describir_helisa(doc)}."
                            f"<br>DIAN: "
                            f"{_describir_dian(reporte, factura, lado)}.",
                            "Corregir el número del documento en HELISA.", 1)
                if doc.get("nit_distinto_revisar"):
                    nh, nd = doc["nit_distinto"]
                    agregar("NIT DISTINTO", dian, filas_h,
                            f"Cruza por prefijo y folio, pero el tercero "
                            f"tiene NIT <b>{nh}</b> en HELISA y <b>{nd}</b> "
                            f"en la DIAN.<br>HELISA: "
                            f"{_describir_helisa(doc)}.",
                            "Verificar el tercero del documento en HELISA.",
                            1)
                if doc["estado"] == "redondeo" and doc.get("nivel") != 4:
                    agregar("REDONDEO", dian, filas_h,
                            f"HELISA y DIAN difieren en "
                            f"<b>{_cop_dian(doc['diferencia'])}</b> "
                            f"(dentro de la tolerancia de "
                            f"{_cop_dian(tolerancia)}).<br>HELISA: "
                            f"{_describir_helisa(doc)}.",
                            "Puede ser el redondeo del IVA por línea en "
                            "HELISA; aun así debe ajustarse para que cuadre "
                            "exacto.", 3)
                if doc.get("dif_iva") is not None and \
                        not dentro_de(doc["dif_iva"],
                                      TOLERANCIA_IVA_DOCUMENTO):
                    agregar("IVA DIFERENTE", dian, filas_h,
                            f"IVA DIAN <b>{_cop_dian(doc['iva_dian'])}</b> "
                            f"vs. IVA en cuentas de IVA de HELISA "
                            f"<b>{_cop_dian(doc['iva'])}</b> (diferencia "
                            f"{_cop_dian(doc['dif_iva'])}).<br>HELISA: "
                            f"{_describir_helisa(doc)}.",
                            "Revisar si el IVA se llevó al costo o al activo "
                            "(mayor valor) o quedó en otra cuenta; explica "
                            "la diferencia de IVA del concepto.", 1)
                if doc.get("descuento") and doc["estado"] != "no_dian":
                    agregar("DESCUENTO COMERCIAL", dian, filas_h,
                            f"HELISA incluye en el total del documento el "
                            f"descuento comercial de <b>"
                            f"{_cop_dian(doc['descuento'])}</b>; la DIAN "
                            f"reporta la factura neta.<br>HELISA: "
                            f"{_describir_helisa(doc)}.",
                            "No requiere ajuste: se resta en la columna NO "
                            "DIAN y en el formato simplificado.", 3)
                if doc.get("asumido") and doc["estado"] not in (
                        "no_dian", "diferencia"):
                    agregar("IMPUESTO ASUMIDO", dian, filas_h,
                            f"HELISA suma al total del documento los "
                            f"impuestos que asume la empresa (<b>"
                            f"{_cop_dian(doc['asumido'])}</b>: rete fuente, "
                            f"ICA… ASUMIDA); la DIAN reporta la factura sin "
                            f"ellos.<br>HELISA: {_describir_helisa(doc)}.",
                            "No requiere ajuste: se resta en la columna NO "
                            "DIAN y en el formato simplificado.", 3)
                if doc.get("no_deducible") and doc["estado"] != "no_dian":
                    agregar("GASTO NO DEDUCIBLE", dian, filas_h,
                            f"El documento tiene una cuenta de gasto no "
                            f"deducible: {_describir_helisa(doc)}.",
                            "Confirmar el tratamiento tributario.", 2)
            for j, factura in enumerate(r["dian"]):
                acuse = (r.get("acuses") or {}).get(id(factura)) or []
                faltan = [f"ACUSE {i + 1}" for i, a in enumerate(acuse)
                          if a == "NO"]
                if faltan:
                    doc = r["dian_a_helisa"].get(j)
                    filas_h = ([m["fila"] for m in doc["movimientos"]]
                               if doc else [])
                    motivo = explicar_acuse_faltante(
                        r.get("info_acuses"), reporte, factura,
                        acuse.index("NO"))
                    agregar("SIN ACUSE", [factura], filas_h,
                            f"Factura a crédito sin evento "
                            f"{', '.join(faltan)} emitido por la empresa "
                            f"en el reporte: "
                            f"{_describir_dian(reporte, factura, lado)}."
                            + (f"<br>Motivo: {html.escape(motivo)}."
                               if motivo else ""),
                            "Confirmar en el portal DIAN (RADIAN) si el "
                            "evento existe; si no, emitirlo. La hoja ACUSES "
                            "del Excel muestra qué evento se tomó para cada "
                            "factura.", 2)
        else:
            informe = r["informe"]
            filas_total = [informe["fila_total_general"]] \
                if informe.get("fila_total_general") else []
            if abs(r["diferencia_total"]) >= 0.01:
                ajustes = "".join(
                    f"<br>{html.escape(a['etiqueta'])}: "
                    f"{_cop_dian(a['valor'])}" for a in r["ajustes"])
                filas_aj = [c["fila"] for a in r["ajustes"]
                            for c in a.get("cuentas", []) if c.get("fila")]
                agregar("DIFERENCIA EN EL TOTAL", list(r["dian"]),
                        filas_total + filas_aj,
                        f"Total DIAN ({len(r['dian'])} documentos): "
                        f"<b>{_cop_dian(r['total_dian'])}</b><br>TOTAL "
                        f"GENERAL HELISA: {_cop_dian(r['total_helisa'])}"
                        f"{ajustes}<br>Diferencia: "
                        f"<b>{_cop_dian(r['diferencia_total'])}</b>.",
                        "Con el informe Resumen no se ve documento por "
                        "documento: carga el Detalle (RELACION) para ubicar "
                        "la partida exacta.", 0)
            if r.get("diferencia_iva") and abs(r["diferencia_iva"]) >= 0.01:
                filas_iva = [c["fila"] for c in r.get("cuentas_iva", [])
                             if c.get("fila")]
                con_iva = [f for f in r["dian"]
                           if numero(dato(reporte, f, "IVA"))]
                agregar("DIFERENCIA DE IVA", con_iva, filas_iva,
                        f"IVA DIAN: <b>{_cop_dian(r['iva_dian'])}</b><br>IVA "
                        f"HELISA (cuentas de IVA): "
                        f"{_cop_dian(r['iva_helisa'])}<br>Diferencia: "
                        f"<b>{_cop_dian(r['diferencia_iva'])}</b>.",
                        "Revisar las cuentas de IVA del comprobante y los "
                        "documentos con IVA en la DIAN.", 1)

        items.sort(key=lambda i: i["orden"])
        for n, item in enumerate(items, start=1):
            item["numero"] = n
            item["etiqueta"] = str(n)
            item["color"] = PALETA_COTEJOS[(n - 1) % len(PALETA_COTEJOS)]
        salida[clave] = items
    return salida


def texto_diferencia_dian(item, fila_dian=None, fila_helisa=None):
    """HTML del globo explicativo de una diferencia DIAN."""
    partes = [f"<b>{html.escape(item['etiqueta'])} · "
              f"{html.escape(item['estado'])}</b>", item["texto"],
              f"<b>Qué hacer:</b> {html.escape(item['que_hacer'])}"]
    ubicacion = []
    if fila_dian:
        ubicacion.append(f"DIAN fila {fila_dian}")
    if fila_helisa:
        ubicacion.append(f"HELISA fila {fila_helisa}")
    if ubicacion:
        partes.append(f"<i>{' · '.join(ubicacion)}</i>")
    return "<br>".join(partes)


def marcas_dian(items, numero_dian, numero_helisa):
    """Marcas {fila: (color, etiqueta)} de cada documento y los globos."""
    marcas_d, marcas_h, tips = {}, {}, {}
    for item in items:
        filas_d = sorted({numero_dian[id(f)] for f in item["dian"]
                          if id(f) in numero_dian})
        filas_h = sorted({numero_helisa[id(f)] for f in item["helisa"]
                          if id(f) in numero_helisa})
        item["filas_dian"], item["filas_helisa"] = filas_d, filas_h
        for fila in filas_d:
            marcas_d.setdefault(fila, (item["color"], item["etiqueta"]))
        for fila in filas_h:
            marcas_h.setdefault(fila, (item["color"], item["etiqueta"]))
        tips[item["etiqueta"]] = texto_diferencia_dian(
            item, filas_d[0] if filas_d else None,
            filas_h[0] if filas_h else None)
    return marcas_d, marcas_h, tips
