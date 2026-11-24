"""Cruce DIAN vs HELISA (sin Streamlit).

Contrato:
  REGLA (v6.5): se concilia SIEMPRE todo el reporte DIAN. Un concepto con
  documentos DIAN y sin documentos en HELISA se concilia contra un HELISA
  vacio (informe_vacio) y cada documento queda como no contabilizado.
  analizar_dian(reporte, informes_helisa, parametros=None) -> dict con resultados por concepto,
      diferencias, documentos solo en DIAN / solo en HELISA y alertas.
  cruzar_compras(...) -> cruce de compras con verificacion de asumidos
      (5315) e IVA (2408).
  clave_documento(texto) -> (prefijo, folio) canonico de un numero de
      documento: sin tipo, ceros de relleno, guiones ni espacios
      ("FEV 00000ABCD1234", "0000ABCD-1240" y DIAN ABCD + 1234 dan
      ("ABCD", "1234")). v6.11.4.

Depende de: gmya.comun.texto, gmya.comun.numeros, gmya.modulos.dian.parametros, gmya.modulos.dian.lectura, gmya.modulos.dian.acuses
"""

import copy
from collections import Counter, OrderedDict, defaultdict

from gmya.comun.texto import alfanumerico, comparable, solo_nit
from gmya.comun.numeros import formato_cop, numero
from gmya.modulos.dian.parametros import (
    dato, dentro_de, PARAMETROS_DIAN_BASE, posibles_no_contabilizadas,
    RUIDO_DECIMAL, TOLERANCIA_IVA_DOCUMENTO,
)
from gmya.modulos.dian.lectura import (
    coincide_cuenta, contiene_palabra, detectar_periodo_dian, es_codigo,
    etiqueta_periodo, filtrar_dian, iva_debito_resumen, leer_helisa,
    nit_empresa_dian, nit_sin_dv, periodo_desde_texto, periodo_dian,
    valor_cuentas,
)
from gmya.modulos.dian.acuses import (
    asignar_acuses_detalle, eventos_emitidos, sugerir_prefijos_acuse,
)


# ------------------------------------------------------------
# Cruce de facturas de compra: detalle HELISA vs DIAN
# ------------------------------------------------------------
def naturaleza_iva(concepto):
    """Lado contable donde HELISA registra el IVA del concepto."""
    if concepto.get("naturaleza_iva"):
        return concepto["naturaleza_iva"]
    emitido = comparable(concepto["grupo"]) == "EMITIDO"
    nota = any("NOTA" in comparable(t) for t in concepto["tipos"])
    # Ventas: IVA generado (credito). Notas credito de proveedores: menor
    # IVA descontable (credito). Compras y documento soporte: debito.
    if (emitido and concepto["clave"] != "DSE") or (nota and not emitido):
        return "credito"
    return "debito"


def usa_acuses(concepto):
    if "acuses" in concepto:
        return bool(concepto["acuses"])
    return (comparable(concepto["grupo"]) == "RECIBIDO"
            and not any("NOTA" in comparable(t) for t in concepto["tipos"]))


def nits_doc(doc):
    """NIT principal del documento y los de todos sus movimientos (un
    pago en efectivo puede registrar al empleado en la primera linea)."""
    if "_nits" not in doc:
        doc["_nits"] = {doc["nit"]} | {solo_nit(m["identidad"])
                                       for m in doc["movimientos"]
                                       if m.get("identidad")}
    return doc["_nits"]


def nit_generico(nit):
    """NIT de relleno que se usa para terceros del exterior o sin NIT
    (444444449, 222222222222, 999999999...): todos los digitos iguales salvo
    quiza el ultimo."""
    digitos = solo_nit(nit)
    return len(digitos) >= 7 and len(set(digitos[:-1])) == 1


def _parecido_nombre(a, b):
    import difflib
    a, b = comparable(a), comparable(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


import re as _re

_RE_CLAVE_DOC = _re.compile(r"^0*([A-Z0-9]*?[A-Z])?0*(\d+)$")


def clave_documento(texto):
    """v6.11.4: (prefijo, folio) canonico de un numero de documento.
    HELISA rellena con ceros y a veces pone guion ("00000ABCD1234",
    "0000ABCD-1240", "000000000NCE0012", "000000012345678"); la DIAN trae
    prefijo y folio aparte (ABCD / 1234, a veces con ceros). Se quitan
    ceros de relleno a la izquierda del prefijo y del folio, guiones y
    espacios. Si el texto no tiene la forma prefijo + numero se devuelve
    (texto, "")."""
    t = alfanumerico(texto)
    m = _RE_CLAVE_DOC.match(t)
    if not m:
        return (t, "")
    return (m.group(1) or "", m.group(2).lstrip("0") or "0")


def cruzar_compras(reporte, facturas_dian, detalle, tolerancia,
                   columna_nit="NIT Emisor", tolerancia_folio=0.0):
    """
    Empareja cada documento del detalle HELISA con una factura DIAN.
    Criterios, en orden de confianza (siempre mismo NIT del proveedor):
      1. prefijo + folio DIAN = numero del documento HELISA
      2. el numero HELISA termina en el folio y empieza por el prefijo
      3. el numero HELISA termina en el folio
      4. mismo valor total, hasta tolerancia_folio (folio mal digitado)
    v6.5: si no cruza por NIT, se acepta el MISMO prefijo + folio con NIT
    distinto cuando uno de los NIT es generico (444444449: clientes y
    proveedores del exterior) o el nombre del tercero coincide; el
    documento queda marcado con doc['nit_distinto'] = (nit HELISA, nit DIAN).
    v6.11.4: comparador de numeros (clave_documento): el numero de HELISA
    y el de la DIAN se comparan ya normalizados (prefijo + folio sin ceros
    de relleno ni guiones). Si el MISMO numero canonico esta una sola vez
    en cada lado y el NIT es distinto (p. ej. EMPRESA D factura al paciente
    menor y HELISA registra al acudiente), se cruzan cuando el documento es
    EMITIDO por la empresa (el numero es unico por ley) o cuando el valor
    es exactamente igual; queda doc['tercero_distinto'] = (HELISA, DIAN) y
    se marca para revisar el tercero.
    Si el documento tiene descuento comercial (doc['descuento'], solo
    ventas) se compara el total con y sin descuento y se toma el que cuadre
    con la DIAN: unas facturas salen netas del descuento y otras no (p. ej.
    un descuento de transporte que se causa aparte).
    """
    docs = list(detalle["documentos"].values())

    def neto_cuentas(doc):
        """v6.5: total del documento sin los cruces internos. Un documento
        que debita y acredita la misma cuenta (p. ej. legalizacion de
        anticipos 133020) suma en TOTAL DOCUMENTO valores que no son de la
        factura; el neto por cuenta deja solo lo que se causa."""
        if "_neto" not in doc:
            por_cuenta = defaultdict(float)
            ambos = defaultdict(lambda: [False, False])
            for m in doc.get("movimientos") or []:
                cuenta = str(m.get("cuenta") or "").strip()
                por_cuenta[cuenta] += (m.get("debito") or 0) \
                    - (m.get("credito") or 0)
                ambos[cuenta][0] |= bool(m.get("debito"))
                ambos[cuenta][1] |= bool(m.get("credito"))
            if any(d and c for d, c in ambos.values()):
                neto = round(sum(v for v in por_cuenta.values() if v > 0), 2)
                doc["_neto"] = neto if neto < round(
                    doc["total_debito"], 2) - RUIDO_DECIMAL else None
            else:
                doc["_neto"] = None
        return doc["_neto"]

    emitido = "RECEPTOR" in columna_nit.upper()

    def cruce_pasivo(doc):
        """v6.11.4: en documentos EMITIDOS (ventas), debitos netos a
        cuentas 25 / 28 (pagos compartidos, copagos, anticipos y avances
        recibidos) que se aplican dentro de la factura: HELISA los suma en
        TOTAL DOCUMENTO y la DIAN trae la factura neta (p. ej. una
        factura con ingresos 13... por el valor neto de la DIAN y un
        copago cruzado contra una cuenta 25...). Solo se usa si al restarlo cuadra con la DIAN."""
        if not emitido:
            return 0.0
        if "_cruce_pasivo" not in doc:
            por_cuenta = defaultdict(float)
            for m in doc.get("movimientos") or []:
                cuenta = str(m.get("cuenta") or "").strip()
                if cuenta.startswith(("25", "28")):
                    por_cuenta[cuenta] += (m.get("debito") or 0) \
                        - (m.get("credito") or 0)
            doc["_cruce_pasivo"] = round(sum(v for v in por_cuenta.values()
                                             if v > 0), 2)
        return doc["_cruce_pasivo"]

    def opciones(doc):
        base = round(doc["total_debito"], 2)
        desc = doc.get("descuento") or 0.0
        asum = doc.get("asumido") or 0.0
        salida = [base]
        if neto_cuentas(doc) is not None:
            salida.append(neto_cuentas(doc))
        if cruce_pasivo(doc):
            salida.append(round(base - cruce_pasivo(doc), 2))
        if desc:
            salida.append(round(base - desc, 2))
        if asum:
            salida.append(round(base - asum, 2))
            if desc:
                salida.append(round(base - desc - asum, 2))
        return salida

    def distancia(doc, total):
        return min(abs(total - t) for t in opciones(doc))

    def total_doc(doc, total_dian):
        return min(opciones(doc), key=lambda t: abs(total_dian - t))
    libres_d = set(range(len(facturas_dian)))
    pareja = {}

    def numero_helisa(doc):
        partes = doc["documento"].split(None, 1)
        resto = partes[1] if len(partes) > 1 else partes[0]
        return alfanumerico(resto)

    columna_nombre = columna_nit.replace("NIT", "Nombre")
    info = []
    for f in facturas_dian:
        info.append({
            "nombre": str(dato(reporte, f, columna_nombre) or ""),
            "nit": solo_nit(dato(reporte, f, columna_nit)),
            "prefijo": alfanumerico(dato(reporte, f, "Prefijo") or ""),
            "folio": alfanumerico(dato(reporte, f, "Folio") or ""),
            "total": round(numero(dato(reporte, f, "Total")), 2),
        })
        info[-1]["clave"] = clave_documento(
            info[-1]["prefijo"] + info[-1]["folio"]) if info[-1]["folio"] \
            else None

    criterios = [
        lambda n, d: n == d["prefijo"] + d["folio"] or (
            d["clave"] is not None and clave_documento(n) == d["clave"]),
        lambda n, d: n.endswith(d["folio"]) and n.startswith(d["prefijo"]),
        lambda n, d: n.endswith(d["folio"]),
    ]

    for nivel, criterio in enumerate(criterios, start=1):
        for i, doc in enumerate(docs):
            if i in pareja:
                continue
            n = numero_helisa(doc)
            candidatos = [j for j in libres_d
                          if info[j]["nit"] in nits_doc(doc)
                          and info[j]["folio"] and criterio(n, info[j])]
            if candidatos:
                j = min(candidatos, key=lambda j: distancia(
                    doc, info[j]["total"]))
                pareja[i] = (j, nivel)
                libres_d.discard(j)

    # v6.5: mismo prefijo + folio, NIT distinto (exterior / NIT generico).
    nit_distinto = {}
    for nivel, criterio in enumerate(criterios, start=1):
        for i, doc in enumerate(docs):
            if i in pareja:
                continue
            n = numero_helisa(doc)
            candidatos = [
                j for j in libres_d if info[j]["folio"] and criterio(
                    n, info[j]) and (
                    nit_generico(doc["nit"]) or nit_generico(info[j]["nit"])
                    or _parecido_nombre(doc.get("beneficiario"),
                                        info[j]["nombre"]) >= 0.8)]
            # Solo si no hay duda: un unico documento DIAN con ese folio.
            if len(candidatos) == 1:
                j = candidatos[0]
                pareja[i] = (j, nivel)
                libres_d.discard(j)
                nit_distinto[i] = (doc["nit"], info[j]["nit"])

    # v6.11.4: mismo numero canonico, NIT distinto (sin nombre parecido).
    tercero_distinto = {}
    por_clave_h = Counter(clave_documento(numero_helisa(d)) for k, d in
                          enumerate(docs) if k not in pareja)
    for i, doc in enumerate(docs):
        if i in pareja:
            continue
        clave = clave_documento(numero_helisa(doc))
        if not clave[1] or len(clave[0] + clave[1]) < 4 or \
                por_clave_h[clave] != 1:
            continue
        candidatos = [j for j in libres_d if info[j]["clave"] == clave]
        if len(candidatos) != 1:
            continue
        j = candidatos[0]
        if not emitido and distancia(doc, info[j]["total"]) > \
                float(tolerancia_folio) + RUIDO_DECIMAL:
            continue
        pareja[i] = (j, 1)
        libres_d.discard(j)
        # En ventas el tercero que cuenta es el de la cartera (debito a
        # 13...): el encabezado del documento puede mostrar la aseguradora
        # de la linea de pagos compartidos (2501).
        nit_h, nombre_h = doc["nit"], str(doc.get("beneficiario") or "")
        if emitido:
            cartera = [m for m in doc.get("movimientos") or []
                       if str(m.get("cuenta") or "").strip().startswith("13")
                       and (m.get("debito") or 0) > 0 and m.get("identidad")]
            if cartera:
                nit_h = solo_nit(cartera[0]["identidad"])
                nombre_h = str(cartera[0].get("beneficiario") or nombre_h)
        nit_distinto[i] = (nit_h, info[j]["nit"])
        tercero_distinto[i] = (f"{nit_h} {nombre_h.strip()}",
                               f"{info[j]['nit']} {info[j]['nombre'].strip()}")

    for i, doc in enumerate(docs):
        if i in pareja:
            continue
        candidatos = [j for j in libres_d
                      if info[j]["nit"] in nits_doc(doc)
                      and distancia(doc, info[j]["total"])
                      <= float(tolerancia_folio) + RUIDO_DECIMAL]
        if len(candidatos) >= 1:
            j = min(candidatos, key=lambda j: distancia(doc, info[j]["total"]))
            pareja[i] = (j, 4)
            libres_d.discard(j)

    for i, doc in enumerate(docs):
        doc["dian"] = None
        doc["nivel"] = None
        doc["estado"] = "no_dian"
        doc["diferencia"] = 0.0
        doc["nit_distinto"] = nit_distinto.get(i)
        doc["tercero_distinto"] = tercero_distinto.get(i)
        doc["nit_distinto_revisar"] = bool(
            doc["nit_distinto"] and not any(
                nit_generico(n) for n in doc["nit_distinto"]))
        doc["cruce_interno"] = 0.0
        if i in pareja:
            j, nivel = pareja[i]
            doc["dian"] = j
            doc["nivel"] = nivel
            comparado = total_doc(doc, info[j]["total"])
            base = round(doc["total_debito"], 2)
            desc = doc.get("descuento") or 0.0
            asum = doc.get("asumido") or 0.0
            if comparado == base:
                doc["descuento"] = 0.0      # la DIAN no lo trae neto
                doc["asumido"] = 0.0
            elif asum and comparado == round(base - asum, 2):
                doc["descuento"] = 0.0
            elif desc and comparado == round(base - desc, 2):
                doc["asumido"] = 0.0
            dif = round(comparado - info[j]["total"], 2)
            neto = neto_cuentas(doc)
            doc["cruce_interno"] = 0.0
            if neto is not None and comparado == neto and abs(dif) <= 1.0:
                # Se compara el neto: el cruce interno no es de la factura
                # (va a NO DIAN); los centavos que queden se reportan.
                doc["cruce_interno"] = round(base - neto, 2)
                doc["descuento"] = doc["asumido"] = 0.0
            elif cruce_pasivo(doc) and comparado == round(
                    base - cruce_pasivo(doc), 2) and dentro_de(dif,
                                                              tolerancia):
                # v6.11.4: pagos compartidos / anticipos (25, 28) cruzados
                # en la factura: verificado contra la DIAN.
                doc["cruce_interno"] = cruce_pasivo(doc)
                doc["cruce_pasivo"] = True
                doc["descuento"] = doc["asumido"] = 0.0
            elif not dentro_de(dif, tolerancia) and comparado != base:
                # v5.7: si ni restando descuento / asumidos cuadra, no se
                # aplican: la diferencia se muestra contra el total HELISA.
                dif = round(base - info[j]["total"], 2)
            doc["diferencia"] = dif
            if abs(dif) < 0.005:
                doc["estado"] = "ok"
            elif dentro_de(dif, tolerancia):
                doc["estado"] = "redondeo"
            else:
                doc["estado"] = "diferencia"

    dian_a_helisa = {pareja[i][0]: docs[i] for i in pareja}
    return docs, dian_a_helisa, info


# ------------------------------------------------------------
# Analisis completo
# ------------------------------------------------------------

def analizar_dian(reporte, informes_helisa, parametros=None):
    """
    reporte          : resultado de leer_reporte_dian
    informes_helisa  : {clave_concepto: informe leido (resumen o detalle)}
    """
    parametros = parametros or copy.deepcopy(PARAMETROS_DIAN_BASE)
    avisos = list(reporte.get("avisos", []))

    # Periodo: se deduce de los documentos (mes, corte, semana, varios)
    info_periodo = detectar_periodo_dian(reporte, informes_helisa,
                                    parametros["conceptos"])
    periodo = info_periodo["mes"]
    etiqueta = info_periodo["etiqueta"]
    periodo_reporte = periodo_dian(reporte)
    meses_inf = {periodo_desde_texto(i.get("meses", ""))
                 for i in informes_helisa.values()} - {None}
    if meses_inf and periodo_reporte and periodo_reporte not in meses_inf:
        avisos.append(
            f"El mes de HELISA ({', '.join(etiqueta_periodo(m) for m in sorted(meses_inf))}) "
            f"no coincide con el mes predominante del reporte DIAN "
            f"({etiqueta_periodo(periodo_reporte)}).")

    # Empresa
    nit_dian = nit_empresa_dian(reporte)
    empresa, nit_helisa = "", ""
    for clave, informe in informes_helisa.items():
        empresa = empresa or informe.get("empresa", "")
        nit_informe = nit_sin_dv(informe.get("nit", ""))
        nit_helisa = nit_helisa or nit_informe
        if nit_dian and nit_informe and nit_informe != nit_dian:
            avisos.append(
                f"El NIT del informe HELISA de {clave} ({nit_informe}) no "
                f"coincide con el NIT de la empresa en el reporte DIAN "
                f"({nit_dian}).")
        periodo_inf = periodo_desde_texto(informe.get("meses", ""))
        if periodo_inf and len(meses_inf) > 1:
            avisos.append(
                f"El informe HELISA de {clave} corresponde a "
                f"{etiqueta_periodo(periodo_inf)}; los informes cargados "
                "son de meses distintos.")

    # v6.9: reclamos (eventos REJECTED / CLAIM que nombran la factura): no
    # son acuse; se avisan para confirmar el tratamiento de la factura.
    try:
        for e in eventos_emitidos(reporte):
            if e.get("factura") and e["prefijo"] in ("REJECTED", "CLAIM"):
                avisos.append(
                    f"RECLAMO: la empresa emitió un reclamo ({e['prefijo']}) "
                    f"a la factura {e['factura']} de {e['nombre']}"
                    + (f" el {e['fecha']:%d/%m/%Y}" if e.get("fecha") else "")
                    + ". No cuenta como acuse. Confirmar si la factura se "
                    "anuló, tiene nota crédito o no debe contabilizarse.")
    except Exception:
        pass

    # Prefijos de acuses (deteccion automatica si no se indicaron)
    sugeridos = sugerir_prefijos_acuse(reporte)
    for numero_acuse in (1, 2):
        llave = f"prefijo_acuse_{numero_acuse}"
        if parametros.get(llave) is None and sugeridos[numero_acuse - 1]:
            parametros[llave] = sugeridos[numero_acuse - 1]

    # v6.5: SIEMPRE se concilia todo el reporte DIAN. Un concepto con
    # documentos en la DIAN y sin informe (o sin documentos en la relacion
    # de HELISA) se concilia contra un HELISA vacio: cada documento DIAN
    # queda como no contabilizado, en rojo, en vez de quedar por fuera.
    informes_helisa = dict(informes_helisa)
    sin_helisa = []
    plantilla = next((i for i in informes_helisa.values()
                      if i.get("clase") == "detalle"), None)
    for concepto in parametros["conceptos"]:
        if concepto["clave"] in informes_helisa:
            continue
        if filtrar_dian(reporte, concepto["grupo"], concepto["tipos"]):
            informes_helisa[concepto["clave"]] = informe_vacio(
                plantilla, concepto)
            sin_helisa.append(concepto["clave"])

    resultados = []
    for concepto in parametros["conceptos"]:
        clave = concepto["clave"]
        informe = informes_helisa.get(clave)
        if informe is None:
            continue
        try:
            facturas = filtrar_dian(reporte, concepto["grupo"], concepto["tipos"])
            resultado = {"concepto": concepto, "informe": informe,
                         "dian": facturas, "etiqueta": etiqueta}

            total_dian = round(sum(numero(dato(reporte, f, "Total"))
                                   for f in facturas), 2)
            iva_dian = round(sum(numero(dato(reporte, f, "IVA"))
                                 for f in facturas), 2)
            resultado.update(total_dian=total_dian, iva_dian=iva_dian)

            # El tipo de informe HELISA (resumen o detalle) se detecta solo:
            # con el detalle (p. ej. las RELACION ...) se cruza documento por
            # documento; con el resumen se comparan totales por cuenta.
            modo = informe["clase"]
            resultado["modo"] = modo
            if modo == "resumen":
                documento_esperado = comparable(
                    concepto.get("documento_helisa", "")).split(" - ")[0]
                codigos = [comparable(c) for c, _ in informe["tipos"]]
                # Vale cualquier codigo HELISA del concepto (FC o FCC...).
                if documento_esperado and codigos and not any(
                        c == documento_esperado
                        or MAPA_CODIGOS_HELISA.get(c) == clave
                        for c in codigos):
                    avisos.append(
                        f"El informe cargado para {clave} es de tipo "
                        f"{', '.join(c + ' - ' + n for c, n in informe['tipos'])}"
                        f"; se esperaba {concepto.get('documento_helisa')}.")
                ajustes = []
                for palabra in concepto.get("ajustes", []):
                    valor, cuentas = valor_cuentas(informe, [palabra])
                    if valor:
                        ajustes.append({
                            "etiqueta": f"MENOS {comparable(palabra)} HELISA",
                            "valor": -valor,
                            "cuentas": cuentas,
                        })
                iva_helisa = None
                if concepto.get("cuentas_iva"):
                    iva_helisa, resultado["cuentas_iva"] = valor_cuentas(
                        informe, concepto["cuentas_iva"],
                        parametros["palabras_excluir_iva"])
                elif naturaleza_iva(concepto) == "debito":
                    # v5.7 (p. ej. DSE): sin cuentas de IVA configuradas se
                    # toma el IVA de las cuentas 2408 (24080212...) que
                    # tenga el informe; la fila DIFERENCIA muestra si cuadra.
                    valor, cuentas = iva_debito_resumen(
                        informe, [p for p in parametros["palabras_iva"]
                                  if es_codigo(p)], iva_dian)
                    if valor:
                        iva_helisa, resultado["cuentas_iva"] = valor, cuentas
                        if not dentro_de(iva_dian - valor, parametros.get(
                                "tolerancia_estado", 0.0)):
                            avisos.append(
                                f"{clave}: el IVA de HELISA en cuentas "
                                f"{', '.join(c['codigo'] for c in cuentas)} "
                                f"({valor:,.2f}) no coincide con el IVA DIAN "
                                f"({iva_dian:,.2f}).")
                # v5.7: impuestos asumidos (cuenta 5315) en el Resumen. Solo
                # se restan si al restarlos el total cuadra con la DIAN o si
                # la cuenta dice ASUMIDO; si no, se avisa y no se tocan.
                total_previo = informe["total_debitos"] + sum(
                    a["valor"] for a in ajustes)
                dif_previa = round(total_dian - total_previo, 2)
                valor_asum, cuentas_asum = valor_cuentas(
                    informe, (parametros.get("cuentas_asumidos") or [])
                    + (parametros.get("palabras_asumidos") or []))
                if valor_asum and naturaleza_iva(concepto) == "debito":
                    tol = float(parametros.get("tolerancia_estado", 0.0)) \
                        + RUIDO_DECIMAL
                    explica = abs(dif_previa + valor_asum) <= tol
                    # v6.5 (opcion intermedia): todo lo de la cuenta 5315 se
                    # toma SIEMPRE como impuestos asumidos; si con eso el
                    # total no cuadra con la DIAN se avisa en pantalla y en
                    # el Excel (antes no se restaba).
                    ajustes.append({
                        "etiqueta": "MENOS IMPUESTOS ASUMIDOS HELISA",
                        "valor": -valor_asum, "tipo": "asumidos",
                        "cuentas": cuentas_asum})
                    if not explica:
                        texto = (
                            f"{clave}: se tomaron {valor_asum:,.2f} de "
                            "impuestos asumidos (cuenta 5315) pero con ellos "
                            "el total no cuadra con la DIAN; revisar si "
                            "todo lo de la 5315 corresponde a este concepto.")
                        avisos.append(texto)
                        resultado["alerta_asumidos"] = texto
                total_helisa = informe["total_debitos"]
                total_ajustado = round(total_helisa
                                       + sum(a["valor"] for a in ajustes), 2)
                resultado.update(
                    total_helisa=total_helisa, ajustes=ajustes,
                    total_helisa_ajustado=total_ajustado,
                    iva_helisa=iva_helisa,
                    diferencia_total=round(total_dian - total_ajustado, 2),
                    diferencia_iva=(round(iva_dian - iva_helisa, 2)
                                    if iva_helisa is not None else None),
                    documentos_helisa=None,
                )
                resultado["posibles"] = posibles_no_contabilizadas(
                    reporte, facturas, resultado["diferencia_total"],
                    resultado["diferencia_iva"],
                    float(parametros.get("tolerancia_estado", 0.0)))
            else:
                columna_nit = ("NIT Receptor"
                               if comparable(concepto["grupo"]) == "EMITIDO"
                               else "NIT Emisor")
                palabras_desc = parametros.get("palabras_descuento") or []
                for doc in informe["documentos"].values():
                    doc["descuento"] = round(sum(
                        m["debito"] - m["credito"] for m in doc["movimientos"]
                        if coincide_cuenta(m["cuenta"], m["nombre"],
                                           palabras_desc)), 2) \
                        if concepto.get("restar_descuentos") else 0.0
                    palabras_asum = parametros.get("palabras_asumidos") or []
                    cuentas_asum = parametros.get("cuentas_asumidos") or []

                    def es_asumido(m):
                        if not m["debito"]:
                            return False
                        if contiene_palabra(m["nombre"], palabras_asum) or \
                                contiene_palabra(m["concepto"], palabras_asum):
                            return True
                        # v5.7: cualquier debito en 5315 es candidato. Solo
                        # se toma como asumido si al restarlo el documento
                        # cuadra con la DIAN (lo verifica cruzar_compras);
                        # si no cuadra, el documento queda con su total.
                        return any(str(m["cuenta"]).strip().startswith(c)
                                   for c in cuentas_asum)
                    movs_asum = [m for m in doc["movimientos"]
                                 if es_asumido(m)] \
                        if naturaleza_iva(concepto) == "debito" else []
                    doc["asumido"] = round(sum(
                        m["debito"] - m["credito"] for m in movs_asum), 2)
                    doc["cuentas_asumido"] = sorted({
                        str(m["cuenta"]).strip() for m in movs_asum})
                    # v6.5: todo lo de la cuenta 5315 (4 primeros digitos)
                    # del documento, antes de verificarlo contra la DIAN.
                    movs_5315 = [m for m in movs_asum if any(
                        str(m["cuenta"]).strip().startswith(str(c)[:4])
                        for c in cuentas_asum)]
                    doc["asumido_5315"] = round(sum(
                        m["debito"] - m["credito"] for m in movs_5315), 2)
                    doc["cuentas_5315"] = sorted({
                        str(m["cuenta"]).strip() for m in movs_5315})
                docs, dian_a_helisa, info = cruzar_compras(
                    reporte, facturas, informe,
                    float(parametros["tolerancia_redondeo"]), columna_nit,
                    float(parametros.get("tolerancia_folio", 0.0)))
                marcar_detalle(docs, parametros, naturaleza_iva(concepto))
                marcar_otro_concepto(reporte, docs, concepto, parametros)
                terceros = [d for d in docs if d.get("tercero_distinto")]
                if terceros:
                    avisos.append(
                        f"{clave}: {len(terceros)} documento(s) cruzados por "
                        "el MISMO número (prefijo y folio) con tercero "
                        "distinto en HELISA y en la DIAN (p. ej. "
                        + "; ".join(f"{d['documento']}: HELISA "
                                    f"{d['tercero_distinto'][0]} / DIAN "
                                    f"{d['tercero_distinto'][1]}"
                                    for d in terceros[:3])
                        + "). Quedan conciliados por número y valor y "
                        "marcados para verificar el tercero.")
                for doc in docs:
                    doc["iva_dian"] = doc["dif_iva"] = None
                    if doc["dian"] is not None:
                        factura = facturas[doc["dian"]]
                        doc["iva_dian"] = round(numero(dato(reporte, factura,
                                                            "IVA")), 2)
                        # v5.7: IVA en cuentas 2408 cuyo nombre se excluye
                        # (p. ej. 24080212 IVA ... RETENIDO en documentos
                        # soporte): se toma solo si asi cuadra con la DIAN.
                        if not dentro_de(doc["iva_dian"] - doc["iva"],
                                         TOLERANCIA_IVA_DOCUMENTO) and \
                                doc.get("iva_amplio") is not None and \
                                dentro_de(doc["iva_dian"] - doc["iva_amplio"],
                                          TOLERANCIA_IVA_DOCUMENTO):
                            doc["iva"] = doc["iva_amplio"]
                            doc["iva_verificado"] = True
                        doc["dif_iva"] = round(doc["iva_dian"] - doc["iva"], 2)
                # Lo que HELISA tiene de mas frente a la DIAN en documentos
                # cruzados: redondeo y descuento comercial (columna NO DIAN).
                for doc in docs:
                    doc["ajuste_nd"] = 0.0
                    if doc["dian"] is not None and (
                            doc["estado"] == "redondeo"
                            or ((doc.get("descuento") or doc.get("asumido"))
                                and doc["estado"] != "diferencia")):
                        doc["ajuste_nd"] = round(doc["total_debito"]
                                                 - info[doc["dian"]]["total"],
                                                 2)
                    elif doc["dian"] is not None and doc.get("cruce_interno"):
                        # v6.5: solo el cruce interno; los centavos que
                        # queden siguen como diferencia del documento.
                        doc["ajuste_nd"] = doc["cruce_interno"]
                descuentos = round(sum(
                    d["descuento"] for d in docs if d.get("descuento")
                    and d["dian"] is not None
                    and d["estado"] != "diferencia"), 2)
                ajustes = ([{"etiqueta": "MENOS DESCUENTOS COMERCIALES HELISA",
                             "valor": -descuentos, "cuentas": []}]
                           if descuentos else [])
                cruces = round(sum(d.get("cruce_interno") or 0 for d in docs
                                   if d["dian"] is not None), 2)
                if cruces:
                    ajustes.append({
                        "etiqueta": "MENOS CRUCES INTERNOS DE CUENTAS "
                                    "(ANTICIPOS / PAGOS COMPARTIDOS) HELISA",
                        "valor": -cruces, "tipo": "cruces", "cuentas": []})
                asumidos = round(sum(
                    d["asumido"] for d in docs if d.get("asumido")
                    and d["dian"] is not None
                    and d["estado"] != "diferencia"), 2)
                if asumidos:
                    ajustes.append({"etiqueta": "MENOS IMPUESTOS ASUMIDOS "
                                                "HELISA",
                                    "valor": -asumidos, "tipo": "asumidos",
                                    "cuentas": sorted({
                                        c for d in docs if d.get("asumido")
                                        and d["dian"] is not None
                                        and d["estado"] != "diferencia"
                                        for c in d.get("cuentas_asumido")
                                        or []})})
                # v6.5 (opcion intermedia): en el formato simplificado la
                # fila IMPUESTOS ASUMIDOS CTA 5315 lleva TODO lo de la 5315.
                # Lo que no se pudo verificar contra un documento DIAN se
                # suma igual y se avisa (pantalla y Excel). No se incluye la
                # 5315 de documentos que cuadran con la DIAN SIN restarla
                # (ahi la DIAN ya la trae dentro del total).
                no_verif = []
                for d in docs:
                    valor_5315 = d.get("asumido_5315") or 0
                    if not valor_5315:
                        continue
                    cuadro_sin = d["dian"] is not None and d["estado"] in (
                        "ok", "redondeo") and not d.get("asumido")
                    if cuadro_sin or (d.get("asumido") and d["dian"]
                                      is not None
                                      and d["estado"] != "diferencia"):
                        continue
                    motivo = ("no está en el reporte DIAN"
                              if d["dian"] is None else
                              "no cuadra con la DIAN al restarla")
                    no_verif.append({"documento": d["documento"],
                                     "valor": valor_5315,
                                     "cuentas": d.get("cuentas_5315") or [],
                                     "motivo": motivo})
                extra_5315 = round(sum(x["valor"] for x in no_verif), 2)
                if extra_5315:
                    detalle_txt = "; ".join(
                        f"{x['documento']} {x['valor']:,.2f} "
                        f"({', '.join(x['cuentas'])}: {x['motivo']})"
                        for x in no_verif[:6])
                    texto = (f"{clave}: {extra_5315:,.2f} de la cuenta 5315 "
                             "están en documentos que no se pudieron "
                             "verificar contra la DIAN y se sumaron igual a "
                             "IMPUESTOS ASUMIDOS en el formato simplificado: "
                             f"{detalle_txt}. Revisar.")
                    avisos.append(texto)
                    resultado["alerta_asumidos"] = texto
                resultado["asumidos_sin_verificar"] = extra_5315
                info_acuses = (asignar_acuses_detalle(
                    reporte, facturas, parametros)
                    if usa_acuses(concepto) else None)
                acuses = info_acuses["marcas"] if info_acuses else {}

                # v6.10.1: impuesto al consumo por documento. Algunos
                # proveedores (p. ej. COLOMBIA TELECOMUNICACIONES) lo
                # discriminan en la factura y en HELISA, pero el reporte
                # DIAN trae INC en 0 (va dentro del total). Si el total
                # cruza, se identifica como INC NO DISCRIMINADO EN DIAN
                # (como las facturas NO DIAN) y se alerta; nunca se asume.
                inc_nd_docs = []
                for j, doc in dian_a_helisa.items():
                    doc["inc_no_discriminado"] = 0.0
                    doc["dif_inc"] = None
                    consumo = round(doc.get("consumo") or 0, 2)
                    inc_d = round(numero(dato(reporte, facturas[j], "INC")),
                                  2)
                    if not consumo or abs(consumo - inc_d) <= RUIDO_DECIMAL:
                        continue
                    if not inc_d and doc["estado"] in ("ok", "redondeo"):
                        doc["inc_no_discriminado"] = consumo
                        inc_nd_docs.append(doc)
                    else:
                        doc["dif_inc"] = (inc_d, consumo)
                inc_no_discriminado = round(sum(
                    d["inc_no_discriminado"] for d in inc_nd_docs), 2)
                if inc_nd_docs:
                    avisos.append(
                        f"{clave}: {len(inc_nd_docs)} documento"
                        f"{'' if len(inc_nd_docs) == 1 else 's'} con "
                        f"impuesto al consumo en HELISA "
                        f"({formato_cop(inc_no_discriminado)}) que el "
                        "reporte DIAN trae con INC en 0 aunque el total "
                        "cuadra (" + ", ".join(sorted({
                            str(d.get("beneficiario") or "").strip()
                            for d in inc_nd_docs}))[:150]
                        + "): se identifican en la fila INC NO DISCRIMINADO "
                        "EN DIAN. Revisar.")
                iva_helisa = round(sum(d["iva"] for d in docs), 2)
                consumo_helisa = round(sum(d["consumo"] for d in docs), 2)
                iva_no_dian = round(sum(d["iva"] for d in docs
                                        if d["estado"] == "no_dian"), 2)
                no_dian = round(sum(d["total_debito"] for d in docs
                                    if d["estado"] == "no_dian")
                                + sum(d["ajuste_nd"] for d in docs), 2)
                total_helisa = informe["total_debitos"]
                total_ajustado = round(total_helisa - no_dian, 2)
                consumo_dian = round(sum(numero(dato(reporte, f, "INC"))
                                         for f in facturas), 2)

                resultado.update(
                    total_helisa=total_helisa, ajustes=ajustes,
                    total_helisa_ajustado=total_ajustado,
                    iva_helisa=round(iva_helisa - iva_no_dian, 2),
                    iva_helisa_bruto=iva_helisa, iva_no_dian=iva_no_dian,
                    consumo_helisa=consumo_helisa, consumo_dian=consumo_dian,
                    inc_no_discriminado=inc_no_discriminado,
                    no_dian=no_dian,
                    diferencia_total=round(total_dian - total_ajustado, 2),
                    diferencia_iva=round(iva_dian - (iva_helisa - iva_no_dian),
                                         2),
                    documentos_helisa=docs, dian_a_helisa=dian_a_helisa,
                    info_dian=info, acuses=acuses, info_acuses=info_acuses,
                )
            avisos.extend(avisos_parecido(resultado))
            resultados.append(resultado)
        except Exception as error:      # un concepto no bloquea a los demas
            avisos.append(f"{clave}: no se pudo conciliar ({error}). Se "
                          "omitió este concepto; revisa el informe cargado.")

    # Documentos DIAN que no entran en ningun concepto (informativo)
    usados = set()
    for concepto in parametros["conceptos"]:
        for f in filtrar_dian(reporte, concepto["grupo"], concepto["tipos"]):
            usados.add(id(f))
    otros = Counter()
    otros_valor = defaultdict(float)
    for r in reporte["registros"]:
        if id(r) in usados:
            continue
        llave = (str(dato(reporte, r, "Grupo")),
                 str(dato(reporte, r, "Tipo de documento")))
        otros[llave] += 1
        otros_valor[llave] += numero(dato(reporte, r, "Total"))
    no_conciliados = [
        {"grupo": g, "tipo": t, "cantidad": n,
         "total": round(otros_valor[(g, t)], 2)}
        for (g, t), n in sorted(otros.items())
    ]

    for r in resultados:
        if r["concepto"]["clave"] not in sin_helisa:
            continue
        folios = [f"{dato(reporte, f, 'Prefijo') or ''}"
                  f"{dato(reporte, f, 'Folio') or ''}" for f in r["dian"]]
        uno = len(r["dian"]) == 1
        avisos.append(
            f"{r['concepto']['clave']} ({r['concepto']['nombre']}): la DIAN "
            f"tiene {len(r['dian'])} documento{'' if uno else 's'} por "
            f"{r['total_dian']:,.2f} ({', '.join(folios[:10])}"
            f"{'…' if len(folios) > 10 else ''}) que NO "
            f"{'está' if uno else 'están'} en HELISA: "
            "quedan como no contabilizados. Si ya se contabilizaron, carga "
            "el informe HELISA de este concepto.")

    return {
        "reporte": reporte,
        "resultados": resultados,
        "periodo": periodo,
        "etiqueta": etiqueta,
        "info_periodo": info_periodo,
        "empresa": empresa,
        "nit": nit_helisa or nit_dian,
        "avisos": avisos,
        "no_conciliados": no_conciliados,
        "parametros": parametros,
    }


def avisos_parecido(resultado):
    """Avisa cuando DIAN y HELISA de un concepto casi no se parecen."""
    clave = resultado["concepto"]["clave"]
    facturas = resultado["dian"]
    salida = []
    if resultado["modo"] == "detalle":
        docs = resultado["documentos_helisa"] or []
        if docs and not facturas:
            salida.append(
                f"{clave}: el reporte DIAN no tiene documentos de este "
                f"concepto ({resultado['concepto']['grupo']}: "
                f"{', '.join(resultado['concepto']['tipos'])}); todo lo de "
                "HELISA queda como NO DIAN. ¿Es el reporte correcto?")
        elif docs and facturas:
            cruzados = len(resultado["dian_a_helisa"])
            fraccion = cruzados / max(len(facturas), len(docs))
            if fraccion < 0.30:
                salida.append(
                    f"{clave}: solo {cruzados} de {max(len(facturas), len(docs))}"
                    f" documentos cruzan entre DIAN y HELISA ({fraccion:.0%})."
                    " Parecen documentos que no corresponden (otro concepto, "
                    "otra empresa u otro periodo).")
    else:
        dian, helisa = resultado["total_dian"], resultado["total_helisa"]
        if facturas and helisa and abs(dian - helisa) > 0.5 * max(
                abs(dian), abs(helisa)):
            salida.append(
                f"{clave}: el total DIAN ({dian:,.2f}) y el de HELISA "
                f"({helisa:,.2f}) son muy distintos. Revisa que el informe "
                "sea del concepto y periodo correctos.")
        elif helisa and not facturas:
            salida.append(
                f"{clave}: el reporte DIAN no tiene documentos de este "
                "concepto pero HELISA sí. ¿Es el reporte correcto?")
    return salida


MAPA_CODIGOS_HELISA = {"FEV": "FV", "FV": "FV", "FE": "FV", "DSE": "DSE",
                       "DS": "DSE", "NDC": "NC", "NC": "NC", "NCC": "NC",
                       "FC": "FC", "FCE": "FC",
                       # v6.4: EMPRESA D y otras empresas usan FCC (factura de
                       # compra por modulo) y DSEC (documento soporte
                       # electronico de compra).
                       "FCC": "FC", "DSEC": "DSE",
                       # v6.11.3: GMYA usa DSEE (documento soporte
                       # electronico).
                       "DSEE": "DSE",
                       # v5.8: notas de ventas y de ajuste al DSE
                       "NCV": "NCV", "NDV": "NDV", "NADSE": "NADSE",
                       # v6.9: tipos de EMPRESA B S.A.S. (lista de documentos de
                       # HELISA). Ventas: factura al detal, servicio de
                       # maquila, consignacion, canales digitales,
                       # empleados, internacionales y venta de activos
                       # fijos; sus notas credito (devolucion) y debito.
                       "FEDU": "FV", "FESM": "FV", "FECO": "FV",
                       "FEDG": "FV", "FEEM": "FV", "FEEX": "FV",
                       "FACT": "FV",
                       "NCFV": "NCV", "NCCO": "NCV", "NCFS": "NCV",
                       "NDFV": "NDV", "NDFS": "NDV", "NDCO": "NDV",
                       "NADS": "NADSE"}
# Orden de los conceptos en pantallas y Excel.
ORDEN_CONCEPTOS = ["FV", "NCV", "NDV", "DSE", "NADSE", "NC", "FC"]


def informe_vacio(plantilla, concepto):
    """Informe HELISA 'Detalle' sin documentos para un concepto que la DIAN
    trae y HELISA no (v6.5). Usa los titulos/columnas de otro informe
    Detalle cargado si lo hay, para que la hoja HELISA se vea igual."""
    base = {"empresa": "", "nit": "", "titulo": "Comprobante diario - "
            "Detalle", "meses": "", "columnas": {}, "anchos": [],
            "fila_encabezado": {"celdas": []}, "filas_titulo": [],
            "total_general": None, "pie": [], "grilla": [],
            "fecha_informe": None}
    if plantilla:
        for llave in base:
            if llave in plantilla:
                base[llave] = copy.deepcopy(plantilla[llave])
        if base.get("total_general"):
            columnas = base["columnas"]
            for celda in base["total_general"].get("celdas", []):
                if celda.get("col") in (columnas.get("debitos"),
                                        columnas.get("creditos")):
                    celda["valor"] = 0.0
        base["pie"] = []
        base["grilla"] = []
    base.update(clase="detalle", cuerpo=[], documentos=OrderedDict(),
                total_debitos=0.0, combinado=True, sin_helisa=True,
                archivo=f"(sin documentos {concepto['clave']} en HELISA)")
    return base


def concepto_de_informe(informe):
    """Concepto (FV, NCV, NDV, DSE, NADSE, NC, FC) segun los documentos
    del informe."""
    codigos = Counter()
    if informe["clase"] == "resumen":
        for codigo, _ in informe.get("tipos", []):
            codigos[comparable(codigo)] += 1
    else:
        for documento in informe.get("documentos", {}):
            partes = str(documento).split()
            if partes:
                codigos[comparable(partes[0])] += 1
    for codigo, _ in codigos.most_common():
        if codigo in MAPA_CODIGOS_HELISA:
            return MAPA_CODIGOS_HELISA[codigo]
    return None


CLAVE_COMBINADO = "TODOS"


# ------------------------------------------------------------
# v6.9: tipos de documento HELISA que no se reconocen se cotejan con la DIAN
# ------------------------------------------------------------
def _filas_dian_por_concepto(reporte, parametros):
    """[(concepto, nit contraparte, prefijo, folio, total)] de todo el
    reporte DIAN, por concepto de la conciliacion."""
    filas = []
    for c in parametros["conceptos"]:
        lado = ("NIT Receptor" if comparable(c["grupo"]) == "EMITIDO"
                else "NIT Emisor")
        for f in filtrar_dian(reporte, c["grupo"], c["tipos"]):
            filas.append((c["clave"], solo_nit(dato(reporte, f, lado)),
                          alfanumerico(dato(reporte, f, "Prefijo") or ""),
                          alfanumerico(dato(reporte, f, "Folio") or ""),
                          numero(dato(reporte, f, "Total"))))
    return filas


def conceptos_que_cruzan(doc, filas_dian):
    """Conceptos DIAN con los que cruza un documento HELISA, sin asumir
    nada: (1) mismo NIT y el numero termina en el folio DIAN, (2) numero
    igual a prefijo+folio (folio de 4+ caracteres) y mismo valor, o (3)
    mismo NIT y mismo valor exacto. Devuelve {concepto: criterio}."""
    partes = str(doc.get("documento", "")).split(None, 1)
    numero_doc = alfanumerico(partes[1]) if len(partes) > 1 else ""
    nits = {n for n in nits_doc(doc) if n}
    valores = {round(doc.get("total_debito") or 0, 2),
               round(doc.get("total_credito") or 0, 2)} - {0}
    encontrados = {}
    for concepto, nit, prefijo, folio, total in filas_dian:
        mismo_valor = any(abs(v - total) <= RUIDO_DECIMAL for v in valores)
        if nit in nits and folio and numero_doc.endswith(folio):
            criterio = "NIT y folio"
        elif folio and len(folio) >= 4 and numero_doc and \
                numero_doc.lstrip("0") == (prefijo + folio).lstrip("0") \
                and mismo_valor:
            criterio = "folio y valor"
        elif nit in nits and mismo_valor:
            criterio = "NIT y valor"
        else:
            continue
        if concepto not in encontrados or criterio == "NIT y folio":
            encontrados[concepto] = criterio
    return encontrados


def asignar_tipos_por_dian(informe, reporte, parametros):
    """Para cada tipo (codigo) de documento del informe combinado coteja sus
    documentos con todo el reporte DIAN. Devuelve:
      asignados  {codigo: concepto} de los tipos NO reconocidos que cruzan
                 con un solo concepto (o mayoritariamente con uno), y de
                 tipos conocidos que la DIAN ubica claramente en otro
      avisos     textos para pantalla y Excel (tipos asignados, tipos que no
                 se pudieron cotejar y tipos conocidos cuyos documentos
                 cruzan con OTRO concepto: solo alerta, no se mueven)."""
    if not reporte or not reporte.get("registros") or \
            informe.get("clase") != "detalle":
        return {}, []
    filas = _filas_dian_por_concepto(reporte,
                                     parametros or PARAMETROS_DIAN_BASE)
    por_codigo = defaultdict(list)
    for clave, doc in informe["documentos"].items():
        partes = str(clave).split()
        por_codigo[comparable(partes[0]) if partes else "?"].append(doc)
    asignados, avisos = {}, []
    for codigo, docs in por_codigo.items():
        votos = Counter()
        criterios = Counter()
        for doc in docs:
            cruces = conceptos_que_cruzan(doc, filas)
            for concepto, criterio in cruces.items():
                votos[concepto] += 1
                criterios[criterio] += 1
        total = round(sum(d.get("total_debito") or 0 for d in docs), 2)
        n = len(docs)
        ndoc = f"{n} documento{'s' if n != 1 else ''}"
        conocido = MAPA_CODIGOS_HELISA.get(codigo)
        if conocido:
            if votos and votos[conocido] == 0:
                otro, k = votos.most_common(1)[0]
                if k * 2 > n and list(votos.values()).count(k) == 1:
                    # La DIAN lo contradice con claridad (mas de la mitad
                    # de sus documentos cruzan con otro concepto y con
                    # ninguno del esperado): se usa lo que dice la DIAN.
                    asignados[codigo] = otro
                    avisos.append(
                        f"REVISAR TIPO {codigo}: normalmente es {conocido}, "
                        f"pero {k} de sus {ndoc} cruzan con la DIAN como "
                        f"{otro} y ninguno como {conocido}; se concilió en "
                        f"{otro}. Confirmar en HELISA a qué corresponde el "
                        f"tipo {codigo} en esta empresa.")
                else:
                    avisos.append(
                        f"REVISAR TIPO {codigo}: se concilia en {conocido} "
                        f"(tipo conocido), pero {k} de sus {ndoc} cruzan "
                        f"con la DIAN como {otro}. Confirmar en HELISA a qué "
                        f"corresponde el tipo {codigo} en esta empresa.")
            continue
        if not votos:
            avisos.append(
                f"TIPO HELISA NO RECONOCIDO {codigo}: {ndoc} por "
                f"{formato_cop(total)} no cruzan con ningún documento del reporte "
                "DIAN (ni por NIT y folio, ni por folio y valor, ni por NIT "
                "y valor); no se concilian. Si es un tipo de facturación, "
                "revisar en HELISA a qué concepto corresponde.")
            continue
        (concepto, k), *resto = votos.most_common()
        if resto and resto[0][1] == k:
            avisos.append(
                f"TIPO HELISA NO RECONOCIDO {codigo}: sus documentos cruzan "
                "con la DIAN en varios conceptos por igual ("
                + ", ".join(f"{c} {v}" for c, v in votos.most_common())
                + f"); no se asigna a ninguno. {ndoc} por {formato_cop(total)} sin "
                "conciliar: revisar en HELISA.")
            continue
        asignados[codigo] = concepto
        como = ", ".join(c for c, _ in criterios.most_common())
        texto = (f"TIPO HELISA NO RECONOCIDO {codigo}: se concilió en "
                 f"{concepto} porque {k} de sus {ndoc} cruzan con documentos "
                 f"DIAN de {concepto} ({como}).")
        if k < n:
            texto += (f" Los {n - k} que no cruzan quedan como no reportados "
                      "en la DIAN dentro de ese concepto.")
        if resto:
            texto += (" Otros cruzan con "
                      + ", ".join(f"{c} ({v})" for c, v in resto)
                      + ": revisar.")
        avisos.append(texto + " Confirmar el tipo en HELISA.")
    return asignados, avisos


def dividir_informe_combinado(informe, asignados=None):
    """
    Un "Comprobante diario - Detalle" de HELISA con todos los tipos de
    documento juntos (FEV, DSE, NDC, FC... la relacion de documentos del
    mes) se separa en un informe por concepto, como si se hubieran
    exportado uno por uno. 'asignados' (v6.9) agrega tipos no reconocidos
    que se cotejaron con la DIAN (asignar_tipos_por_dian). Devuelve ({concepto: informe}, {codigo: n} de
    los documentos que no son de ningun concepto).
    """
    if informe.get("clase") != "detalle":
        raise ValueError(
            "El informe combinado debe ser el «Comprobante diario - Detalle» "
            "de HELISA (con todos los tipos de documento); el Resumen no "
            "se puede separar por concepto.")
    concepto_de = {}
    sin_concepto = Counter()
    for clave in informe["documentos"]:
        partes = str(clave).split()
        codigo = comparable(partes[0]) if partes else ""
        concepto = (asignados or {}).get(codigo) or \
            MAPA_CODIGOS_HELISA.get(codigo)
        concepto_de[clave] = concepto
        if not concepto:
            sin_concepto[codigo or "?"] += 1
    partes_informe = {}
    columnas = informe["columnas"]
    for concepto in [c for c in dict.fromkeys(concepto_de.values()) if c]:
        documentos = OrderedDict(
            (k, d) for k, d in informe["documentos"].items()
            if concepto_de.get(k) == concepto)
        cuerpo = [(t, f, k) for t, f, k in informe["cuerpo"]
                  if concepto_de.get(k) == concepto]
        debitos = round(sum(d["total_debito"] or 0
                            for d in documentos.values()), 2)
        creditos = round(sum(d["total_credito"] or 0
                             for d in documentos.values()), 2)
        total_general = None
        if informe.get("total_general"):
            # Fila TOTAL GENERAL con los totales de este concepto.
            total_general = copy.deepcopy(informe["total_general"])
            for celda in total_general["celdas"]:
                if celda["col"] == columnas.get("debitos"):
                    celda["valor"] = debitos
                elif celda["col"] == columnas.get("creditos"):
                    celda["valor"] = creditos
        parte = dict(informe)
        parte.update(documentos=documentos, cuerpo=cuerpo,
                     total_debitos=debitos, total_general=total_general,
                     combinado=True,
                     archivo=f"{informe.get('archivo', '')} ({concepto})")
        partes_informe[concepto] = parte
    return partes_informe, dict(sin_concepto)


def resumen_informe_combinado(contenido, nombre=""):
    """[(concepto, documentos, total)] para mostrar al cargar el archivo."""
    informe = leer_helisa(contenido, nombre)
    partes, otros = dividir_informe_combinado(informe)
    orden = ORDEN_CONCEPTOS
    filas = sorted(((c, len(p["documentos"]), p["total_debitos"])
                    for c, p in partes.items()),
                   key=lambda x: orden.index(x[0]) if x[0] in orden else 9)
    return filas, otros


def marcar_detalle(docs, parametros, naturaleza="debito"):
    """Calcula IVA, impuesto al consumo y observaciones por documento."""
    for doc in docs:
        doc["iva"] = 0.0
        doc["consumo"] = 0.0
        doc["no_deducible"] = False
        amplio = 0.0
        for mov in doc["movimientos"]:
            if naturaleza == "credito":
                valor, lado = mov["credito"] - mov["debito"], "credito"
            else:
                valor, lado = mov["debito"] - mov["credito"], "debito"
            mov["lado_iva"] = lado
            mov["es_iva"] = (
                coincide_cuenta(mov["cuenta"], mov["nombre"],
                                parametros["palabras_iva"])
                and not contiene_palabra(mov["nombre"],
                                         parametros["palabras_excluir_iva"])
                and mov[lado] != 0)
            mov["es_consumo"] = (
                contiene_palabra(mov["nombre"],
                                 parametros["palabras_consumo"])
                and mov[lado] != 0)
            if mov["es_iva"]:
                doc["iva"] += valor
            if coincide_cuenta(mov["cuenta"], mov["nombre"],
                               parametros["palabras_iva"]) and mov[lado]:
                amplio += valor
                mov["es_iva_amplio"] = True
            if mov["es_consumo"]:
                doc["consumo"] += valor
            if contiene_palabra(mov["nombre"],
                                parametros["palabras_no_deducible"]):
                doc["no_deducible"] = True
        doc["iva"] = round(doc["iva"], 2)
        doc["iva_amplio"] = round(amplio, 2)
        doc["consumo"] = round(doc["consumo"], 2)


def marcar_otro_concepto(reporte, docs, concepto, parametros):
    """
    Documentos del informe que son de otro concepto (p. ej. una nota NDC
    dentro del informe de compras FC): si no cruzaron, se buscan en los
    documentos DIAN de ese concepto para no decir que "no estan en la DIAN".
    """
    otros = {c["clave"]: c for c in parametros["conceptos"]
             if c["clave"] != concepto["clave"]}
    for doc in docs:
        doc["otro_concepto"] = None
        if doc["estado"] != "no_dian":
            continue
        codigo = comparable(str(doc["documento"]).split()[0]) \
            if str(doc["documento"]).split() else ""
        clave = MAPA_CODIGOS_HELISA.get(codigo)
        if not clave or clave == concepto["clave"] or clave not in otros:
            continue
        otro = otros[clave]
        lado = ("NIT Receptor" if comparable(otro["grupo"]) == "EMITIDO"
                else "NIT Emisor")
        numero_doc = alfanumerico(str(doc["documento"]).split(None, 1)[-1])
        texto = f"ES {clave}"
        for f in filtrar_dian(reporte, otro["grupo"], otro["tipos"]):
            if solo_nit(dato(reporte, f, lado)) not in nits_doc(doc):
                continue
            folio = alfanumerico(dato(reporte, f, "Folio") or "")
            prefijo = alfanumerico(dato(reporte, f, "Prefijo") or "")
            if (folio and numero_doc.endswith(folio)) or abs(
                    numero(dato(reporte, f, "Total"))
                    - doc["total_debito"]) <= RUIDO_DECIMAL:
                texto = (f"ES {clave}: EN LA DIAN COMO {prefijo}{folio} "
                         f"({dato(reporte, f, 'Tipo de documento')})")
                break
        doc["otro_concepto"] = texto


def observacion_documento(doc, info_dian):
    partes = []
    if doc["no_deducible"]:
        partes.append("GASTO NO DEDUCIBLE")
    if doc["estado"] == "no_dian" and doc.get("otro_concepto"):
        partes.append(f"NO ES {doc['documento'].split()[0]} "
                      f"({doc['otro_concepto']}); SE RESTA AQUÍ")
    elif doc["estado"] == "no_dian":
        partes.append("NO REPORTADA EN DIAN")
    elif doc["estado"] == "redondeo":
        partes.append("REDONDEO VS DIAN")
    elif doc["estado"] == "diferencia":
        partes.append(f"DIFERENCIA DE VALOR VS DIAN ({doc['diferencia']:,.2f})")
    if doc.get("dif_iva") is not None and not dentro_de(
            doc["dif_iva"], TOLERANCIA_IVA_DOCUMENTO):
        partes.append(f"IVA DIAN {doc['iva_dian']:,.2f} VS HELISA "
                      f"{doc['iva']:,.2f}: REVISAR SI EL IVA SE LLEVÓ AL "
                      "COSTO O AL ACTIVO")
    if doc.get("descuento") and doc["estado"] != "no_dian":
        partes.append(f"DESCUENTO COMERCIAL INCLUIDO EN HELISA "
                      f"({doc['descuento']:,.2f})")
    if doc.get("asumido") and doc["estado"] not in ("no_dian",
                                                     "diferencia"):
        partes.append(f"IMPUESTOS ASUMIDOS INCLUIDOS EN HELISA "
                      f"({doc['asumido']:,.2f})")
    if doc.get("cruce_interno") and doc.get("cruce_pasivo"):
        partes.append(f"PAGOS COMPARTIDOS / ANTICIPOS (CUENTAS 25-28) "
                      f"CRUZADOS EN LA FACTURA: SE COMPARA EL NETO "
                      f"{doc['total_debito'] - doc['cruce_interno']:,.2f}; "
                      f"CRUCE {doc['cruce_interno']:,.2f} A NO DIAN")
    elif doc.get("cruce_interno"):
        partes.append(f"DOCUMENTO CON CRUCE DE CUENTAS (P. EJ. ANTICIPOS): "
                      f"SE COMPARA EL NETO "
                      f"{doc['total_debito'] - doc['cruce_interno']:,.2f}; "
                      f"CRUCE {doc['cruce_interno']:,.2f} A NO DIAN")
    if doc.get("inc_no_discriminado"):
        partes.append(f"IMPUESTO AL CONSUMO {doc['inc_no_discriminado']:,.2f}"
                      " NO DISCRIMINADO EN LA DIAN (EL TOTAL CUADRA)")
    elif doc.get("dif_inc"):
        partes.append(f"INC DIAN {doc['dif_inc'][0]:,.2f} VS HELISA "
                      f"{doc['dif_inc'][1]:,.2f}: REVISAR")
    if doc.get("tercero_distinto"):
        th, td = doc["tercero_distinto"]
        partes.append(f"MISMO NÚMERO DE DOCUMENTO CON TERCERO DISTINTO: "
                      f"HELISA {th} / DIAN {td}: VERIFICAR TERCERO EN HELISA")
    elif doc.get("nit_distinto"):
        nh, nd = doc["nit_distinto"]
        partes.append(f"NIT EN HELISA {nh} VS DIAN {nd}"
                      + (" (TERCERO DEL EXTERIOR / NIT GENÉRICO)"
                         if nit_generico(nh) or nit_generico(nd)
                         else ": VERIFICAR TERCERO EN HELISA"))
    if doc.get("nivel") == 4 and doc["dian"] is not None:
        d = info_dian[doc["dian"]]
        partes.append(f"FOLIO DIAN {d['prefijo']}{d['folio']}: VERIFICAR "
                      "NUMERO EN HELISA")
    return " / ".join(partes)
