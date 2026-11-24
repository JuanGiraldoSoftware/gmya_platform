"""Modo "todo en uno": un solo informe HELISA combinado (FV, FC, DSE, NC, ND,
NCV, NDV, NADSE) contra el reporte DIAN.

Contrato:
  generar_conciliacion_dian(contenido_dian, archivos_helisa, parametros=None,
      nombre_dian=, contenido_eventos=None) -> dict con 'analisis' y el
      Excel generado (ver docstring de la funcion).

Depende de: gmya.comun.texto, gmya.modulos.dian.parametros, gmya.modulos.dian.lectura, gmya.modulos.dian.acuses, gmya.modulos.dian.analisis, gmya.modulos.dian.excel
"""

import io
import re

from collections import OrderedDict

from gmya.comun.texto import comparable
from gmya.modulos.dian.parametros import (
    alerta_documento_dian, AMARILLO, dentro_de, AZUL_ALERTA, AZUL_ASUMIDOS, CIAN_REVISADO,
    CONVENCIONES_DIAN, dato, FORMATO_CONTABLE, LETRA_ROJA_ALERTA,
    resaltar_si_no_es_cero, ROJO_ALERTA, VERDE_ENCABEZADO,
)
from gmya.modulos.dian.lectura import (
    combinar_reportes_dian, expandir_archivos, leer_helisa, leer_reporte_dian,
    parece_reporte_dian, SINONIMOS_DIAN,
)
from gmya.modulos.dian.acuses import eventos_de_reporte
from gmya.modulos.dian.analisis import (
    analizar_dian, asignar_tipos_por_dian, CLAVE_COMBINADO,
    concepto_de_informe, dividir_informe_combinado, MAPA_CODIGOS_HELISA,
    usa_acuses,
)
from gmya.modulos.dian.excel import (
    construir_excel_dian, _convenciones, _hoja_acuses,
)


# ============================================================
# FORMATO SIMPLIFICADO (una sola hoja: DIAN vs. SISTEMA por concepto)
# ============================================================
ORDEN_SIMPLIFICADO = ["FV", "NCV", "NDV", "DSE", "NADSE", "FC", "NC"]


def valores_sistema(resultado):
    """Totales HELISA (sistema) por concepto para el formato simplificado:
    IVA, impuesto al consumo, total y ajustes que se restan."""
    if resultado["modo"] == "resumen":
        return {"iva": resultado.get("iva_helisa"), "inc": None,
                "total": resultado["total_helisa"],
                "ajustes": resultado.get("ajustes") or []}
    return {"iva": resultado.get("iva_helisa_bruto"),
            "inc": resultado.get("consumo_helisa"),
            "total": resultado["total_helisa"],
            "ajustes": resultado.get("ajustes") or []}


def construir_excel_simplificado(analisis):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter as L

    reporte = analisis["reporte"]
    encabezados = list(reporte["encabezados"])
    # Columnas que agrega el formato completo despues de "Forma de Pago":
    # FORMA DE PAGO2 (contado / credito) y los 3 acuses (v4.6).
    posicion = encabezados.index("Forma de Pago") + 1 \
        if "Forma de Pago" in encabezados else len(encabezados)
    extra = ["FORMA DE PAGO2", "ACUSE 1", "ACUSE 2", "ACUSE 3"]
    cabecera = (encabezados[:posicion] + extra + encabezados[posicion:]
                + ["CONCILIACIÓN SISTEMA"])
    formas = {str(k): v for k, v in
              analisis["parametros"]["formas_pago"].items()}

    def col(nombre):
        return cabecera.index(nombre) + 1

    c_obs = len(cabecera)
    c_iva = col("IVA") if "IVA" in encabezados else col("Total")
    c_inc = col("INC") if "INC" in encabezados else None
    c_total = col("Total")
    c_etq = c_iva - 1
    columnas_valor = set(reporte["columnas_valor"])

    def relleno(color):
        return PatternFill("solid", fgColor=color)

    normal = Font(name="Calibri", size=11, color="000000")
    negrita = Font(name="Calibri", size=11, bold=True, color="000000")
    roja = Font(name="Calibri", size=11, bold=True, color="FF0000")
    blanca = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

    wb = Workbook()
    hoja = wb.active
    hoja.title = f"DIAN {analisis['etiqueta']}"[:31]
    hoja.sheet_properties.tabColor = VERDE_ENCABEZADO

    for c, titulo in enumerate(cabecera, start=1):
        x = hoja.cell(1, c, titulo)
        x.font = blanca
        x.fill = relleno(VERDE_ENCABEZADO)
        x.alignment = Alignment(horizontal="center", vertical="center",
                                wrap_text=True)
    for nombre in extra:                 # como en el formato completo
        hoja.cell(1, col(nombre)).fill = relleno(CIAN_REVISADO)
        hoja.cell(1, col(nombre)).font = negrita
    hoja.row_dimensions[1].height = 30

    def formato_valores(r, fuente=None):
        for c in range(1, c_obs + 1):
            x = hoja.cell(r, c)
            if fuente:
                x.font = fuente
            if c >= c_iva and c <= c_total:
                x.number_format = FORMATO_CONTABLE

    resultados = sorted(
        analisis["resultados"],
        key=lambda r: (ORDEN_SIMPLIFICADO.index(r["concepto"]["clave"])
                       if r["concepto"]["clave"] in ORDEN_SIMPLIFICADO
                       else 99))
    fila = 1
    for numero_bloque, resultado in enumerate(resultados):
        concepto = resultado["concepto"]
        fila += 1 if numero_bloque == 0 else 4
        titulo = (f"{concepto['clave']} - {concepto['nombre'].upper()}  "
                  f"({len(resultado['dian'])} documento"
                  f"{'' if len(resultado['dian']) == 1 else 's'} DIAN)")
        hoja.cell(fila, 1, titulo)
        for c in range(1, c_obs + 1):
            hoja.cell(fila, c).fill = relleno("272526")
            hoja.cell(fila, c).font = blanca

        dian_a_helisa = resultado.get("dian_a_helisa") or {}
        info = resultado.get("info_dian") or []
        detalle = resultado["modo"] == "detalle"
        primera = fila + 1
        con_acuses = usa_acuses(concepto)
        for j, factura in enumerate(resultado["dian"]):
            fila += 1
            forma = formas.get(str(dato(reporte, factura, "Forma de Pago"))
                               .strip(), "")
            acuse = list((resultado.get("acuses") or {}).get(
                id(factura), ["", "", ""]) if con_acuses else [])
            acuse = (acuse + ["", "", ""])[:3]
            valores = (list(factura[:posicion]) + [forma] + acuse
                       + list(factura[posicion:len(encabezados)]))
            for c, valor in enumerate(valores, start=1):
                hoja.cell(fila, c, valor)
            for c_acuse in (col("ACUSE 1"), col("ACUSE 2"), col("ACUSE 3")):
                if hoja.cell(fila, c_acuse).value == "NO":
                    hoja.cell(fila, c_acuse).font = Font(
                        name="Calibri", size=11, bold=True, color="FF0000")
            formato_valores(fila, normal)
            color, texto, alerta = alerta_documento_dian(
                resultado, j, factura, reporte)
            if detalle and dian_a_helisa.get(j) is None:
                texto = "NO ESTÁ EN EL SISTEMA"
            texto = texto.replace("HELISA", "EL SISTEMA")
            if texto:
                hoja.cell(fila, c_obs, texto)
            # En el simplificado solo se pintan las alertas (lo conciliado
            # queda sin color, como en el modelo de la firma).
            if alerta or color == ROJO_ALERTA:
                for c in range(1, c_obs + 1):
                    hoja.cell(fila, c).fill = relleno(color)
                hoja.cell(fila, c_obs).font = Font(
                    name="Calibri", size=11, bold=True,
                    color=LETRA_ROJA_ALERTA)
        ultima = max(fila, primera)
        if fila < primera:
            fila += 1
            hoja.cell(fila, 1, "Sin documentos en el reporte DIAN para "
                      "este concepto.").font = Font(name="Calibri", size=11,
                                                    italic=True)

        # Impuestos asumidos (cuenta 5315): como en el modelo de la firma
        # van ANTES del total, del lado DIAN, y se suman al TOTAL para
        # compararlo con el SISTEMA. Solo aparecen si se verificaron (al
        # sumarlos el documento o el total cuadra).
        sistema = valores_sistema(resultado)
        asumidos = [a for a in sistema["ajustes"]
                    if a.get("tipo") == "asumidos"]
        sistema["ajustes"] = [a for a in sistema["ajustes"]
                              if a.get("tipo") != "asumidos"]
        f_asum = None
        # v6.5: tambien lo de la 5315 que no se pudo verificar (opcion
        # intermedia: se suma igual y se deja la alerta en la fila).
        extra_5315 = resultado.get("asumidos_sin_verificar") or 0.0
        if asumidos or extra_5315:
            fila += 1
            f_asum = fila
            codigos = sorted({str(c.get("codigo") if isinstance(c, dict)
                                  else c)[:4]
                              for a in asumidos for c in a.get("cuentas")
                              or []} | ({"5315"} if extra_5315 else set())) \
                or ["5315"]
            hoja.cell(fila, c_etq, "IMPUESTOS ASUMIDOS CTA "
                      + ", ".join(codigos))
            hoja.cell(fila, c_total, round(-sum(a["valor"]
                                                for a in asumidos)
                                           + extra_5315, 2))
            formato_valores(fila, normal)
            for c in range(1, c_obs + 1):
                hoja.cell(fila, c).fill = relleno(AZUL_ASUMIDOS)
            hoja.cell(fila, c_obs, "Impuestos asumidos registrados en el "
                      "sistema; la DIAN reporta los documentos sin ellos.")
            if resultado.get("alerta_asumidos"):
                hoja.cell(fila, c_obs,
                          "⚠ REVISAR: " + resultado["alerta_asumidos"])
                hoja.cell(fila, c_obs).font = Font(
                    name="Calibri", size=11, bold=True,
                    color=LETRA_ROJA_ALERTA)

        # v6.5: FACTURAS NO DIAN (pedido del equipo, p. ej. EMCALI): los
        # documentos del sistema que no estan en el reporte DIAN se suman
        # del lado DIAN antes del TOTAL, como los impuestos asumidos, para
        # que la DIFERENCIA muestre solo lo que falta explicar. Siguen
        # listados abajo en azul para revisarlos.
        f_nodian = None
        no_dian_docs = [d for d in (resultado.get("documentos_helisa")
                                    or []) if d["estado"] == "no_dian"] \
            if detalle else []
        if no_dian_docs:
            fila += 1
            f_nodian = fila
            hoja.cell(fila, c_etq, "FACTURAS NO DIAN")
            hoja.cell(fila, c_iva, round(sum(d["iva"] for d in no_dian_docs),
                                         2))
            if c_inc:
                hoja.cell(fila, c_inc, round(sum(d["consumo"]
                                                 for d in no_dian_docs), 2))
            hoja.cell(fila, c_total, round(sum(d["total_debito"]
                                               for d in no_dian_docs), 2))
            formato_valores(fila, normal)
            for c in range(1, c_obs + 1):
                hoja.cell(fila, c).fill = relleno(AZUL_ALERTA)
            nombres = ", ".join(sorted({str(d["beneficiario"]).strip()
                                        for d in no_dian_docs}))[:180]
            hoja.cell(fila, c_obs, f"{len(no_dian_docs)} documento"
                      f"{'' if len(no_dian_docs) == 1 else 's'} del sistema "
                      f"que no {'está' if len(no_dian_docs) == 1 else 'están'}"
                      f" en el reporte DIAN ({nombres}); ver "
                      "lista abajo.")

        # v6.10.1: impuesto al consumo que el sistema discrimina y la DIAN
        # trae dentro del total con INC en 0 (p. ej. COLOMBIA
        # TELECOMUNICACIONES): se suma del lado DIAN en la columna INC.
        f_incnd = None
        inc_nd_docs = [d for d in (resultado.get("documentos_helisa") or [])
                       if d.get("inc_no_discriminado")] if detalle else []
        if inc_nd_docs and c_inc:
            fila += 1
            f_incnd = fila
            hoja.cell(fila, c_etq, "INC NO DISCRIMINADO EN DIAN")
            hoja.cell(fila, c_inc, round(sum(d["inc_no_discriminado"]
                                             for d in inc_nd_docs), 2))
            formato_valores(fila, normal)
            for c in range(1, c_obs + 1):
                hoja.cell(fila, c).fill = relleno(AZUL_ALERTA)
            nombres = ", ".join(sorted({str(d["beneficiario"]).strip()
                                        for d in inc_nd_docs}))[:150]
            hoja.cell(fila, c_obs,
                      f"Impuesto al consumo de {len(inc_nd_docs)} documento"
                      f"{'' if len(inc_nd_docs) == 1 else 's'} ("
                      + ", ".join(str(d["documento"]).split()[-1]
                                  for d in inc_nd_docs)[:120]
                      + f") de {nombres}: el sistema lo discrimina y la DIAN "
                      "lo reporta dentro del total (INC en 0). El total del "
                      "documento cuadra. Revisar.")

        # TOTAL DIAN
        fila += 1
        f_total = fila
        hoja.cell(fila, c_etq, "TOTAL")
        for c in range(c_iva, c_total + 1):
            hoja.cell(fila, c,
                      f"=SUBTOTAL(109,{L(c)}{primera}:{L(c)}{ultima})"
                      + (f"+{L(c)}{f_asum}" if f_asum and c == c_total
                         else "")
                      + (f"+{L(c)}{f_nodian}" if f_nodian and (
                          c in (c_iva, c_inc, c_total)) else "")
                      + (f"+{L(c)}{f_incnd}" if f_incnd and c == c_inc
                         else ""))
        for c in range(c_etq, c_total + 1):
            hoja.cell(fila, c).fill = relleno(AMARILLO)
        formato_valores(fila, negrita)

        # SISTEMA (HELISA)
        fila += 1
        f_sistema = fila
        hoja.cell(fila, c_etq, "SISTEMA")
        if sistema["iva"] is not None:
            hoja.cell(fila, c_iva, sistema["iva"])
        if c_inc and sistema["inc"] is not None:
            hoja.cell(fila, c_inc, sistema["inc"])
        hoja.cell(fila, c_total, sistema["total"])
        formato_valores(fila, negrita)
        filas_ajuste = []
        for ajuste in sistema["ajustes"]:
            fila += 1
            filas_ajuste.append(fila)
            hoja.cell(fila, c_etq, ajuste["etiqueta"].replace("HELISA",
                                                              "SISTEMA"))
            hoja.cell(fila, c_total, ajuste["valor"])
            formato_valores(fila, normal)

        # DIFERENCIA
        fila += 1
        hoja.cell(fila, c_etq, "DIFERENCIA")
        for c in range(c_iva, c_total + 1):
            restar = "".join(f"-{L(c)}{r}" for r in filas_ajuste)
            hoja.cell(fila, c, f"=+{L(c)}{f_total}-{L(c)}{f_sistema}{restar}")
        formato_valores(fila, None)
        for c in range(c_etq, c_total + 1):
            hoja.cell(fila, c).font = roja
        tolerancia = float(analisis["parametros"].get("tolerancia_estado",
                                                      0.0))
        resaltar_si_no_es_cero(hoja, f"{L(c_iva)}{fila}:{L(c_total)}{fila}",
                               tolerancia)
        if not detalle and not dentro_de(resultado["diferencia_total"],
                                         tolerancia):
            fila += 1
            if resultado.get("posibles"):
                nota = ("Informe Resumen: las filas en MORADO son las que "
                        "explican la diferencia por valor; confirmar con el "
                        "Detalle.")
            else:
                nota = ("Informe Resumen: no permite saber qué documentos "
                        "faltan. Cargar el Comprobante diario - Detalle o la "
                        "RELACION para verlos resaltados.")
            hoja.cell(fila, 1, "⚠ " + nota).font = Font(
                name="Calibri", size=11, bold=True, color=LETRA_ROJA_ALERTA)

        if resultado.get("alerta_asumidos"):
            fila += 1
            hoja.cell(fila, 1, "⚠ " + resultado["alerta_asumidos"]).font = \
                Font(name="Calibri", size=11, bold=True,
                     color=LETRA_ROJA_ALERTA)

        # Documentos del sistema que no estan en el reporte DIAN
        if detalle:
            faltan = [d for d in resultado["documentos_helisa"]
                      if d["estado"] == "no_dian"]
            if faltan:
                fila += 2
                hoja.cell(fila, 1, "EN EL SISTEMA PERO NO EN EL REPORTE "
                          "DIAN (sumados arriba en FACTURAS NO DIAN):")
                hoja.cell(fila, 1).font = negrita
                emitido = comparable(concepto["grupo"]) == "EMITIDO"
                c_nit = col("NIT Receptor" if emitido else "NIT Emisor")
                c_nom = c_nit + 1
                c_folio = col("Folio")
                c_fecha = col("Fecha Emisión") \
                    if "Fecha Emisión" in encabezados else None
                for doc in faltan:
                    fila += 1
                    hoja.cell(fila, c_folio, doc["documento"])
                    if c_fecha:
                        hoja.cell(fila, c_fecha, doc["fecha"])
                    hoja.cell(fila, c_nit, doc["nit"])
                    hoja.cell(fila, c_nom, doc["beneficiario"])
                    hoja.cell(fila, c_iva, doc["iva"])
                    if c_inc:
                        hoja.cell(fila, c_inc, doc["consumo"])
                    hoja.cell(fila, c_total, doc["total_debito"])
                    hoja.cell(fila, c_obs, doc.get("otro_concepto")
                              or "NO ESTÁ EN EL REPORTE DIAN")
                    formato_valores(fila, normal)
                    for c in range(1, c_obs + 1):
                        hoja.cell(fila, c).fill = relleno(AZUL_ALERTA)
                    hoja.cell(fila, c_obs).font = Font(
                        name="Calibri", size=11, bold=True,
                        color=LETRA_ROJA_ALERTA)

    # Convenciones de color
    fila += 3
    fila = _convenciones(hoja, fila, relleno, [
        (c, t.replace("HELISA", "el sistema")) for c, t in CONVENCIONES_DIAN
        if c != CIAN_REVISADO])

    # Nota final con el periodo detectado
    fila += 2
    info_periodo = analisis.get("info_periodo") or {}
    hoja.cell(fila, 1, f"Periodo conciliado: "
              f"{info_periodo.get('descripcion', analisis['etiqueta'])}")
    hoja.cell(fila, 1).font = Font(name="Calibri", size=10, italic=True)
    for aviso in analisis["avisos"]:
        fila += 1
        hoja.cell(fila, 1, "Aviso: " + aviso).font = Font(
            name="Calibri", size=10, color="C00000")

    anchos = {"Tipo de documento": 26, "CUFE/CUDE": 12, "Folio": 13,
              "Prefijo": 8, "Divisa": 7, "Forma de Pago": 8,
              "Medio de Pago": 8, "Fecha Emisión": 12,
              "Fecha Recepción": 19, "NIT Emisor": 12, "Nombre Emisor": 32,
              "NIT Receptor": 12, "Nombre Receptor": 34, "IVA": 15,
              "INC": 13, "Total": 16, "Estado": 24, "Grupo": 10,
              "FORMA DE PAGO2": 11, "ACUSE 1": 9, "ACUSE 2": 9,
              "ACUSE 3": 9, "CONCILIACIÓN SISTEMA": 46}
    for c, titulo in enumerate(cabecera, start=1):
        hoja.column_dimensions[L(c)].width = anchos.get(
            titulo, 14 if titulo in columnas_valor else 11)
    hoja.freeze_panes = "A2"
    _hoja_acuses(wb, analisis, relleno)

    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def generar_conciliacion_dian(contenido_dian, archivos_helisa,
                              parametros=None, nombre_dian="DIAN.xlsx",
                              contenido_eventos=None,
                              ordenar_automatico=False):
    """
    contenido_dian : bytes del reporte DIAN, o lista [(nombre, bytes)] con
                     uno o varios reportes (.xlsx, .zip tal como se descarga
                     del portal, .xls o .csv).
    archivos_helisa: {clave_concepto: (nombre_archivo, bytes)}; cada informe
                     puede ser Excel 97-2003 (XML o binario) o PDF de HELISA.
    contenido_eventos: [(nombre, bytes)] reportes DIAN posteriores (p. ej.
                     del mes siguiente) de los que SOLO se toman los
                     eventos emitidos, para encontrar acuses dados despues
                     de la descarga. Sus facturas no se concilian.
    ordenar_automatico: decision del usuario (v6.7). False (por defecto):
                     cada archivo se usa en el cuadro donde se cargo y solo
                     se avisa si parece de otro. True: si un archivo parece
                     de otro cuadro (reporte DIAN en un cuadro de HELISA,
                     informe de FC en el cuadro de NC...), se ubica solo.
    """
    avisos = []
    archivos_helisa = dict(archivos_helisa)
    if isinstance(contenido_dian, (bytes, bytearray)):
        fuentes = [(nombre_dian, bytes(contenido_dian))]
    else:
        fuentes = [(n, bytes(c)) for n, c in (contenido_dian or [])]
    fuentes = expandir_archivos(fuentes)

    # 1. Si el reporte DIAN quedo en una ranura de HELISA, se intercambia
    #    (solo con "Ordenar automaticamente"; si no, solo se avisa).
    if fuentes and not ordenar_automatico and not any(
            parece_reporte_dian(c) for _, c in fuentes):
        for clave, (nombre, contenido) in archivos_helisa.items():
            if parece_reporte_dian(contenido):
                avisos.append(
                    f"«{nombre}» (cargado en {clave}) parece el reporte DIAN "
                    f"y lo cargado como reporte DIAN no lo parece. Se usaron "
                    "tal como se cargaron; activa «Ordenar automáticamente» "
                    "o cámbialos de cuadro.")
                break
    elif fuentes and not any(parece_reporte_dian(c) for _, c in fuentes):
        for clave, (nombre, contenido) in archivos_helisa.items():
            if parece_reporte_dian(contenido):
                nombre_malo, contenido_malo = fuentes[0]
                avisos.append(
                    f"«{nombre}» (cargado en {clave}) parece el reporte DIAN "
                    f"y «{nombre_malo}» no; se usaron intercambiados.")
                archivos_helisa[clave] = (nombre_malo, contenido_malo)
                fuentes = [(nombre, contenido)] + fuentes[1:]
                break
    elif len(fuentes) > 1:
        quedan = []
        for nombre, contenido in fuentes:
            if parece_reporte_dian(contenido):
                quedan.append((nombre, contenido))
            else:
                avisos.append(f"«{nombre}» se cargó como reporte DIAN pero no "
                              "lo parece; se omitió.")
        fuentes = quedan

    reportes = []
    for nombre, contenido in fuentes:
        try:
            reportes.append(leer_reporte_dian(contenido, nombre))
        except ValueError as error:
            avisos.append(f"{error} («{nombre}»)")
    if reportes:
        reporte = combinar_reportes_dian(reportes)
    else:
        reporte = {
            "archivo": nombre_dian, "hoja": "DIAN",
            "encabezados": list(SINONIMOS_DIAN),
            "indice": {c: i for i, c in enumerate(SINONIMOS_DIAN)},
            "registros": [], "anchos": {},
            "columnas_valor": ["IVA", "INC", "Total"],
            "avisos": ["No se pudo leer el reporte DIAN. Se concilió con un "
                       "reporte DIAN vacío."]}

    # 1b. Reportes posteriores: solo aportan eventos para los acuses.
    if contenido_eventos:
        adicionales = []
        for nombre, contenido in expandir_archivos(
                [(n, bytes(c)) for n, c in contenido_eventos]):
            try:
                extra = leer_reporte_dian(contenido, nombre)
            except ValueError as error:
                avisos.append(f"Eventos posteriores: {error} («{nombre}»)")
                continue
            adicionales.extend(eventos_de_reporte(extra, origen=nombre))
        reporte["eventos_adicionales"] = adicionales
        avisos.append(f"Se tomaron {len(adicionales)} eventos emitidos de "
                      "los reportes posteriores, solo para los acuses.")

    # 2. Informes HELISA: se leen los que se puedan y se ubican en el
    #    concepto que realmente son (si su ranura correcta esta libre).
    leidos = []
    combinado = archivos_helisa.pop(CLAVE_COMBINADO, None)
    for clave, (nombre, contenido) in archivos_helisa.items():
        try:
            informe = leer_helisa(contenido, nombre)
        except Exception as error:
            if parece_reporte_dian(contenido):
                avisos.append(f"«{nombre}» (cargado en {clave}) parece otro "
                              "reporte DIAN, no un informe de HELISA; se "
                              "omitió.")
            else:
                avisos.append(f"No se pudo leer «{nombre}» (cargado en "
                              f"{clave}) como informe de HELISA: {error} El "
                              f"concepto {clave} no se concilió.")
            continue
        leidos.append((clave, concepto_de_informe(informe), nombre, informe))

    informes = {}
    for clave, detectado, nombre, informe in leidos:
        if detectado in (None, clave) or not ordenar_automatico:
            informes[clave] = informe
            if detectado not in (None, clave):
                avisos.append(
                    f"«{nombre}» se cargó en {clave} pero sus documentos "
                    f"parecen de {detectado}. Se concilió en {clave}, tal "
                    "como se cargó; activa «Ordenar automáticamente» para "
                    f"que se ubique en {detectado}, o cámbialo de cuadro.")
    # v6.9: tipos HELISA no reconocidos dentro de un informe cargado por
    # concepto: se concilian en ese cuadro (como se cargo) y se avisa; si
    # sus documentos cruzan con la DIAN en OTRO concepto, alerta de revision.
    for clave, detectado, nombre, informe in leidos:
        try:
            if informe.get("clase") == "resumen":
                codigos = {comparable(c): n for c, n in informe.get("tipos", [])}
            else:
                codigos = {}
                for k in informe.get("documentos", {}):
                    partes = str(k).split()
                    if partes:
                        codigos.setdefault(comparable(partes[0]), "")
            raros = [c for c in codigos if c not in MAPA_CODIGOS_HELISA]
            if not raros:
                continue
            asignados = {}
            if informe.get("clase") == "detalle":
                solo = dict(informe, documentos=OrderedDict(
                    (k, d) for k, d in informe["documentos"].items()
                    if comparable(str(k).split()[0]) in raros))
                asignados, _ = asignar_tipos_por_dian(solo, reporte,
                                                      parametros)
            texto = (f"«{nombre}» (cargado en {clave}) trae tipos de "
                     "documento HELISA no reconocidos: "
                     + ", ".join(c + (f" - {codigos[c]}" if codigos[c] else "")
                                 for c in raros)
                     + f"; se concilian en {clave}, tal como se cargó.")
            distintos = {c: a for c, a in asignados.items() if a != clave}
            if distintos:
                texto += (" REVISAR: según la DIAN "
                          + ", ".join(f"{c} parece {a}"
                                      for c, a in distintos.items())
                          + ".")
            avisos.append(texto)
        except Exception:
            pass

    if combinado:
        nombre_c, contenido_c = combinado
        try:
            informe_c = leer_helisa(contenido_c, nombre_c)
            # v6.9: tipos de documento no reconocidos se cotejan con la DIAN
            # (NIT, folio, valor) y se concilian en el concepto con el que
            # cruzan; los conocidos que cruzan con otro concepto se alertan.
            try:
                asignados, avisos_tipos = asignar_tipos_por_dian(
                    informe_c, reporte, parametros)
            except Exception as error:
                asignados, avisos_tipos = {}, [
                    "No se pudieron cotejar con la DIAN los tipos de "
                    f"documento no reconocidos: {error}"]
            avisos.extend(avisos_tipos)
            partes, otros = dividir_informe_combinado(informe_c, asignados)
            for concepto, parte in partes.items():
                if concepto in informes or any(
                        d == concepto for _, d, _, _ in leidos):
                    avisos.append(
                        f"{concepto}: se usó el informe cargado aparte para "
                        f"ese concepto, no la parte de «{nombre_c}».")
                    continue
                leidos.append((concepto, concepto, nombre_c, parte))
                informes[concepto] = parte
            # Los tipos ya explicados en las alertas de cotejo no se repiten.
            otros = {c: n for c, n in otros.items()
                     if not any(f" {c}:" in a for a in avisos_tipos)}
            if otros:
                avisos.append(
                    f"«{nombre_c}» trae documentos de tipos que no son de "
                    "ningún concepto y no cruzan con la DIAN; se omitieron: "
                    + ", ".join(f"{c} ({n})" for c, n in otros.items())
                    + ".")
        except Exception as error:
            avisos.append(f"No se pudo leer «{nombre_c}» como informe "
                          f"combinado de HELISA: {error}")
    for clave, detectado, nombre, informe in leidos:
        if detectado in (None, clave) or not ordenar_automatico:
            continue
        if detectado not in informes:
            informes[detectado] = informe
            avisos.append(f"«{nombre}» se cargó en {clave} pero sus "
                          f"documentos son de {detectado}; se concilió como "
                          f"{detectado}.")
        elif clave not in informes:
            informes[clave] = informe
            avisos.append(f"«{nombre}» se cargó en {clave} pero parece de "
                          f"{detectado}; se concilió en {clave}. Revisa que "
                          "sea el informe correcto.")
        else:
            avisos.append(f"«{nombre}» (cargado en {clave}, parece de "
                          f"{detectado}) se omitió porque ambos conceptos "
                          "ya tienen informe.")
    if not informes:
        avisos.append("No quedó ningún informe de HELISA para conciliar: el "
                      "resultado solo muestra el reporte DIAN.")

    analisis = analizar_dian(reporte, informes, parametros)
    analisis["avisos"] = avisos + analisis["avisos"]
    # v6.5: los dos Excel se generan SIEMPRE; si uno falla por un caso no
    # previsto, el otro se entrega igual y se avisa (nunca sin documento).
    archivo = simplificado = None
    fallas = []
    try:
        archivo = construir_excel_dian(analisis)
    except Exception as error:
        fallas.append(f"formato completo ({type(error).__name__}: {error})")
    try:
        simplificado = construir_excel_simplificado(analisis)
    except Exception as error:
        fallas.append(f"formato simplificado ({type(error).__name__}: "
                      f"{error})")
    if archivo is None and simplificado is None:
        raise RuntimeError("No se pudo armar ningún Excel: "
                           + "; ".join(fallas))
    if fallas:
        analisis["avisos"].append(
            "No se pudo armar el " + " ni el ".join(fallas) + "; se entrega "
            "el otro formato con la misma conciliación. Avisa al "
            "administrador para revisar el caso.")
        archivo = archivo or simplificado
        simplificado = simplificado or archivo
    empresa = re.sub(r"[^A-Z0-9 ]", "", comparable(analisis["empresa"]))
    empresa = empresa.split(" SAS")[0].split(" S A S")[0].strip()
    palabras = empresa.split()
    corto = " ".join(palabras[:1]) if palabras else "EMPRESA"
    info = analisis["info_periodo"]
    if info["tipo"] == "mes":
        periodo_txt = f"MES DE {analisis['etiqueta']}"
    else:
        periodo_txt = analisis["etiqueta"]
        if str(info["fin"].year) not in periodo_txt:
            periodo_txt += f" {info['fin'].year}"
    nombre = f"CONCILIACION DIAN {periodo_txt} {corto}.xlsx"
    nombre_simple = f"CONCILIACION DIAN {periodo_txt} {corto} SIMPLIFICADA.xlsx"
    return {"archivo": archivo, "nombre_archivo": nombre,
            "archivo_simplificado": simplificado,
            "nombre_simplificado": nombre_simple,
            "analisis": analisis}
