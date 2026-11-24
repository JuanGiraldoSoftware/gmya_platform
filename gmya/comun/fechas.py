"""Nombres de meses en espanol (MESES_ES completos y MES_CORTO abreviados).

Depende de: (solo biblioteca estandar / terceros)
"""



# ============================================================
# CONCILIACION DIAN: REPORTE DE DOCUMENTOS DIAN vs. COMPROBANTES HELISA
# ============================================================
# Entradas : reporte de documentos electronicos descargado de la DIAN
#            (obligatorio) y al menos uno de los informes HELISA FV, DSE,
#            NC o FC (Excel 97-2003 XML o binario). Cada informe puede ser
#            el Comprobante de diario - Resumen o el Comprobante diario -
#            Detalle (las "RELACION ..."): el sistema reconoce cual es.
# Periodo  : se deduce solo (mes completo, corte "AL 19 OCT", semana o
#            varios meses) con detectar_periodo_dian().
# Salidas  : 1) formato completo de la firma (hoja DIAN original, hojas
#               DIAN/HELISA por concepto, resumen) y
#            2) formato simplificado de una hoja (TOTAL / SISTEMA /
#               DIFERENCIA por concepto).
# Todo es parametrizable en PARAMETROS_DIAN_BASE y desde la interfaz.
MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}


MES_CORTO = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
             "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]
