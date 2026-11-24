"""Datos del panel de diferencias de la conciliacion DIAN (v6.14, sin
Streamlit). Modelo: gmya/ui/visual.py (panel de diferencias).

Contrato:
  panel_diferencias_dian(analisis) -> [concepto] con:
    total_a = TOTAL HELISA, total_b = TOTAL DIAN (columna Total del
    reporte), composicion que suma EXACTO total_a - total_b:
      explicada: documentos solo en HELISA (NO DIAN), cruces internos /
        pagos compartidos, descuentos comerciales, impuestos asumidos,
        redondeos (lo que la plataforma ya verifico y resta en el Excel);
      pendiente: diferencias de valor, documentos DIAN no contabilizados
        y lo que quede sin explicar (= diferencia de la conciliacion).
    partidas: una por documento con algo que revisar (valor, solo en un
      lado, IVA, gasto no deducible, folio...). grupos: lo explicado que no
      necesita revisarse uno a uno (redondeos, tercero distinto, cruces).
  conteo_documentos(r) -> (conciliados, por_revisar, no_contabilizados,
      solo_helisa) de un concepto.
Regla: la composicion se arma con los mismos valores del analisis; si no
suma, la UI lo muestra como "Sin explicar" (nunca se esconde).

Depende de: gmya.modulos.dian.analisis, gmya.modulos.dian.excel,
gmya.modulos.dian.parametros
"""

from gmya.comun.numeros import formato_cop
from gmya.modulos.dian.analisis import observacion_documento
from gmya.modulos.dian.excel import estado_concepto
from gmya.modulos.dian.parametros import TOLERANCIA_IVA_DOCUMENTO, dentro_de


def _r2(v):
    return round(float(v or 0), 2)


def _revisar(doc):
    return (doc.get("estado") == "diferencia" or doc.get("no_deducible")
            or doc.get("nit_distinto_revisar") or doc.get("nivel") == 4
            or (doc.get("dif_iva") is not None and not dentro_de(
                doc["dif_iva"], TOLERANCIA_IVA_DOCUMENTO))
            or doc.get("dif_inc"))


def _solo_tercero(d):
    """Cuadra en valor y solo cambia el tercero (EMPRESA D: acudiente vs
    paciente): conciliado con observacion, no partida por revisar."""
    return bool(d.get("tercero_distinto")) and d.get("estado") != \
        "diferencia" and not d.get("no_deducible") and d.get("nivel") != 4 \
        and (d.get("dif_iva") is None or dentro_de(
            d["dif_iva"], TOLERANCIA_IVA_DOCUMENTO)) and not d.get("dif_inc")


def conteo_documentos(r):
    """(conciliados, con observacion, por_revisar, no_contabilizados,
    solo_helisa) de un concepto con informe Detalle; None si es Resumen."""
    docs = r.get("documentos_helisa") or []
    cruces = r.get("dian_a_helisa")
    if r.get("modo") != "detalle" or not isinstance(cruces, dict):
        return None
    ok = obs = rev = 0
    for doc in cruces.values():
        if _solo_tercero(doc):
            obs += 1
        elif _revisar(doc):
            rev += 1
        else:
            ok += 1
    sin = len(r["dian"]) - len(cruces)
    solo = sum(1 for d in docs if d.get("estado") == "no_dian")
    return ok, obs, rev, sin, solo


def _numero(doc):
    partes = str(doc.get("documento", "")).split(None, 1)
    return partes[1].strip() if len(partes) > 1 else partes[0]


def _concepto_detalle(r, analisis):
    info = r.get("info_dian") or []
    docs = r.get("documentos_helisa") or []
    cruces = r.get("dian_a_helisa") or {}
    comp, partidas, grupos = [], [], []

    # --- Explicado: lo que va a NO DIAN en el Excel ---
    solo_h = [d for d in docs if d.get("estado") == "no_dian"]
    if solo_h:
        comp.append({"etiqueta": "Registrados solo en HELISA (NO DIAN)",
                     "valor": _r2(sum(d["total_debito"] for d in solo_h)),
                     "tipo": "explicada", "n": len(solo_h)})
    categorias = [
        ("cruce", "Cruces internos y pagos compartidos (se compara el neto)"),
        ("descuento", "Descuentos comerciales incluidos en HELISA"),
        ("asumido", "Impuestos asumidos incluidos en HELISA"),
        ("redondeo", "Redondeos frente a la DIAN"),
    ]
    por_cat = {k: [] for k, _ in categorias}
    for d in docs:
        if d.get("dian") is None or not d.get("ajuste_nd"):
            continue
        if d.get("cruce_interno"):
            por_cat["cruce"].append(d)
        elif d.get("estado") == "redondeo":
            por_cat["redondeo"].append(d)
        elif d.get("descuento"):
            por_cat["descuento"].append(d)
        elif d.get("asumido"):
            por_cat["asumido"].append(d)
        else:
            por_cat["redondeo"].append(d)
    for k, etiqueta in categorias:
        if por_cat[k]:
            comp.append({"etiqueta": etiqueta, "valor": _r2(sum(
                d["ajuste_nd"] for d in por_cat[k])), "tipo": "explicada",
                "n": len(por_cat[k])})

    # --- Pendiente: la diferencia de la conciliacion ---
    dif_docs = [d for d in docs if d.get("estado") == "diferencia"
                and d.get("dian") is not None]
    if dif_docs:
        comp.append({"etiqueta": "Diferencias de valor por documento",
                     "valor": _r2(sum(d["diferencia"] for d in dif_docs)),
                     "tipo": "pendiente", "n": len(dif_docs)})
    sin_h = [j for j in range(len(r["dian"])) if j not in cruces]
    if sin_h:
        comp.append({"etiqueta": "Documentos DIAN no contabilizados en HELISA",
                     "valor": -_r2(sum(info[j]["total"] for j in sin_h)),
                     "tipo": "pendiente", "n": len(sin_h)})

    # --- Partidas ---
    for d in docs:
        nota = observacion_documento(d, info)
        sub = f"{d.get('beneficiario', '')} · NIT {d.get('nit', '')} · " \
              f"{d.get('fecha', '')}"
        if d.get("estado") == "no_dian":
            partidas.append({
                "id": d["documento"], "titulo": _numero(d), "sub": sub,
                "causa": "Solo en HELISA (NO DIAN)", "tipo": "solo_a",
                "a": _r2(d["total_debito"]), "b": None, "nota": nota,
                "detalle": [("Documento", d["documento"], "—"),
                            ("Total", _r2(d["total_debito"]), "—")]})
            continue
        if d.get("dian") is None or not _revisar(d):
            continue
        if _solo_tercero(d):
            continue            # va en el grupo "Mismo numero, tercero..."
        f = info[d["dian"]]
        comparado = _r2(f["total"] + d.get("diferencia", 0))
        if d.get("estado") == "diferencia":
            causa, tipo = "Diferencia de valor", "valor"
        elif d.get("dif_iva") is not None and not dentro_de(
                d["dif_iva"], TOLERANCIA_IVA_DOCUMENTO):
            causa, tipo = "IVA diferente", "otro"
        elif d.get("no_deducible"):
            causa, tipo = "Gasto no deducible", "otro"
        elif d.get("nit_distinto_revisar"):
            causa, tipo = "Tercero distinto", "otro"
        elif d.get("nivel") == 4:
            causa, tipo = "Folio distinto", "otro"
        else:
            causa, tipo = "Revisar", "otro"
        detalle = [("Documento", d["documento"], f"{f['prefijo']}{f['folio']}",
                    d.get("nivel") == 4),
                   ("Tercero", f"{d.get('nit', '')} {d.get('beneficiario', '')}"
                    .strip(), f"{f['nit']} {f['nombre']}".strip(),
                    bool(d.get("nit_distinto"))),
                   ("Total comparado", comparado, _r2(f["total"]))]
        if d.get("iva_dian") is not None:
            detalle.append(("IVA", _r2(d.get("iva")), _r2(d.get("iva_dian"))))
        partidas.append({
            "id": d["documento"], "titulo": _numero(d), "sub": sub,
            "causa": causa, "tipo": tipo,
            "a": comparado if tipo == "valor" else None,
            "b": _r2(f["total"]) if tipo == "valor" else None,
            "nota": nota, "detalle": detalle})
    for j in sin_h:
        f = info[j]
        partidas.append({
            "id": f"{f['prefijo']}{f['folio']}",
            "titulo": f"{f['prefijo']}{f['folio']}",
            "sub": f"{f['nombre']} · NIT {f['nit']}",
            "causa": "No contabilizado en HELISA", "tipo": "solo_b",
            "a": None, "b": _r2(f["total"]),
            "nota": "Está en el reporte DIAN y no se encontró en HELISA: "
                    "contabilizarlo o verificar si se registró con otro "
                    "número, NIT o periodo.",
            "detalle": [("Documento", "—", f"{f['prefijo']}{f['folio']}"),
                        ("Total", "—", _r2(f["total"]))]})

    # --- Grupos (no hace falta revisarlos uno a uno) ---
    terceros = [d for d in docs if d.get("dian") is not None
                and _solo_tercero(d)]
    if terceros:
        grupos.append({"etiqueta": "Mismo número, tercero distinto",
                       "n": len(terceros), "valor": _r2(sum(
                           d["total_debito"] for d in terceros)),
                       "tipo": "info",
                       "nota": "Mismo número y valor que la DIAN: conciliados; "
                               "revisar el tercero en HELISA."})
    for k, etiqueta in categorias:
        if por_cat[k]:
            grupos.append({"etiqueta": etiqueta, "n": len(por_cat[k]),
                           "valor": _r2(sum(d["ajuste_nd"] for d in por_cat[k])),
                           "tipo": "explicada",
                           "nota": "Verificado contra la DIAN documento por "
                                   "documento; va a la columna NO DIAN."})
    return comp, partidas, grupos


def panel_diferencias_dian(analisis):
    salida = []
    for r in analisis["resultados"]:
        clave = r["concepto"]["clave"]
        total_a, total_b = _r2(r["total_helisa"]), _r2(r["total_dian"])
        conteo = conteo_documentos(r)
        if conteo:
            comp, partidas, grupos = _concepto_detalle(r, analisis)
            ok, obs, rev, sin, solo = conteo
            dona = [("Conciliados", ok, "ok"),
                    ("Conciliados, revisar tercero", obs, "info"),
                    ("Por revisar", rev, "alerta"),
                    ("No contabilizados en HELISA", sin, "error")]
        else:
            # Informe Resumen: no hay detalle por documento.
            explicada = _r2(total_a - _r2(r.get("total_helisa_ajustado",
                                                 total_a)))
            comp = ([{"etiqueta": "Ajustes del informe (ajuste al peso, "
                      "asumidos, descuentos)", "valor": explicada,
                      "tipo": "explicada", "n": None}] if explicada else [])
            comp.append({"etiqueta": "Diferencia del total (informe Resumen: "
                         "cargar el Detalle para verla por documento)",
                         "valor": _r2(-r["diferencia_total"]),
                         "tipo": "pendiente", "n": None})
            partidas, grupos = [], []
            dona = [("Documentos DIAN", len(r["dian"]), "neutro")]
            solo = 0
        estado = estado_concepto(r, analisis["parametros"])
        salida.append({
            "clave": clave, "nombre": r["concepto"]["nombre"],
            "sub": f"{analisis.get('etiqueta', '')} · {len(r['dian'])} "
                   f"documentos DIAN · {estado}",
            "lado_a": "HELISA", "lado_b": "DIAN",
            "total_a": total_a, "total_b": total_b,
            "dona": dona, "centro": f"{len(r['dian']):,}".replace(",", "."),
            "centro_sub": "documentos DIAN",
            "datos": [("Total DIAN", _fmt(total_b)),
                      ("Total HELISA", _fmt(total_a)),
                      ("Diferencia conciliación", _fmt(r["diferencia_total"])),
                      ("Diferencia IVA", "—" if r.get("diferencia_iva") is None
                       else _fmt(r["diferencia_iva"]))],
            "composicion": [x for x in comp if abs(x["valor"]) >= 0.005],
            "partidas": partidas, "grupos": grupos,
            "solo_helisa": solo, "estado": estado,
        })
    return salida


def _fmt(v):
    return formato_cop(v)
