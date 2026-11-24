"""Plantilla de carga de la nomina electronica (DIAN) que
usa la firma (filas 1 a 6, columnas A..DV). Extraido del archivo trabajado
de EMPRESA G (igual en EMPRESA H). Solo datos: no tiene logica.
v6.11.1: LAYOUT_NE_B64 es el layout de carga de la firma tal cual (el que
se usa para generar); CABECERA_NE queda como referencia.

Depende de: (nada)
"""

CABECERA_NE = {'anchos': {'A': 34.0,
            'AA': 17.0,
            'AB': 17.0,
            'AC': 10.7265625,
            'AF': 18.0,
            'AG': 10.7265625,
            'AH': 18.7265625,
            'AI': 12.1796875,
            'AJ': 18.7265625,
            'AK': 21.7265625,
            'AL': 19.81640625,
            'AM': 16.7265625,
            'AN': 17.26953125,
            'AO': 17.26953125,
            'AP': 15.1796875,
            'AQ': 24.54296875,
            'AR': 13.26953125,
            'AS': 19.1796875,
            'AT': 12.54296875,
            'AU': 8.7265625,
            'AX': 8.7265625,
            'AY': 15.7265625,
            'AZ': 16.54296875,
            'B': 33.0,
            'BD': 19.1796875,
            'BE': 19.1796875,
            'BG': 19.1796875,
            'BH': 19.453125,
            'BI': 19.453125,
            'BL': 19.453125,
            'BN': 38.453125,
            'BO': 17.1796875,
            'BP': 17.1796875,
            'BQ': 18.54296875,
            'BS': 13.453125,
            'BU': 13.453125,
            'BV': 13.453125,
            'BW': 13.453125,
            'BX': 13.453125,
            'BY': 29.1796875,
            'BZ': 29.1796875,
            'C': 28.0,
            'CA': 24.453125,
            'CB': 16.26953125,
            'CF': 15.54296875,
            'CH': 15.54296875,
            'CI': 16.26953125,
            'CK': 25.7265625,
            'CL': 26.1796875,
            'CN': 14.1796875,
            'CO': 32.453125,
            'CP': 22.7265625,
            'CQ': 13.81640625,
            'CR': 12.453125,
            'CS': 11.26953125,
            'CT': 16.0,
            'CU': 25.54296875,
            'CW': 28.26953125,
            'CY': 31.0,
            'D': 48.1796875,
            'DB': 14.453125,
            'DH': 16.453125,
            'DI': 33.1796875,
            'DJ': 14.453125,
            'DK': 28.26953125,
            'DL': 15.1796875,
            'DS': 15.1796875,
            'DT': 37.54296875,
            'DU': 38.26953125,
            'DV': 33.453125,
            'E': 22.0,
            'F': 43.7265625,
            'G': 61.1796875,
            'H': 25.81640625,
            'J': 4.0,
            'K': 35.0,
            'L': 24.54296875,
            'M': 14.1796875,
            'N': 13.453125,
            'O': 13.54296875,
            'P': 16.0,
            'Q': 20.1796875,
            'R': 17.26953125,
            'S': 11.1796875,
            'T': 9.0,
            'U': 17.1796875,
            'V': 16.1796875,
            'W': 14.0,
            'X': 22.7265625,
            'Y': 15.54296875,
            'Z': 20.26953125},
 'filas': [[None, None, 'SOPORTE DE NÓMINA', None, None, None, None, None,
            None, None, None, 'SOPORTE DE NÓMINA', None, None,
            'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None, None,
            'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None, None,
            None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None,
            None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None,
            None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None,
            None, None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA',
            None, None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA',
            None, None, None, 'SOPORTE DE NÓMINA', None, None, None,
            'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None, None,
            'SOPORTE DE NÓMINA', None, None, None, 'SOPORTE DE NÓMINA', None,
            None, None, None, 'SOPORTE DE NÓMINA', None, None, None, None,
            'SOPORTE DE NÓMINA', None, None, None, None, 'SOPORTE DE NÓMINA',
            None, None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA',
            None, 'SOPORTE DE NÓMINA', None, None, 'SOPORTE DE NÓMINA', None,
            None, 'SOPORTE DE NÓMINA', None, None, None, 'SOPORTE DE NÓMINA',
            None, None, None, 'SOPORTE DE NÓMINA', None, None, None,
            'SOPORTE DE NÓMINA', None, None, None, None, 'SOPORTE DE NÓMINA',
            None, None, None, None, None, None],
           ['INFORMACION GENERAL*', None, None, None, None, None, None,
            'NOVEDAD (opcional) (Aplica solo para TipoNómina: 02 (NOMINA '
            'INDIVIDUAL CON NOVEDAD))',
            'NOTA DE AJUSTE (reemplazar) (Este campo se visualizará solo para '
            'TipoNomina: 03 (NOTA DE AJUSTE (reemplazar))',
            None, None, 'PERIODO*', None, None, None, None, None, ' PAGO*',
            None, ' PAGO*', None, 'FechasPago *', None, None, None, None,
            'DEVENGADOS*', None, None, 'DEVENGADOS*', None, None, None,
            'DEVENGADOS*', None, 'DEVENGADOS*', None, 'DEVENGADOS*', None,
            None, None, 'DEVENGADOS*', None, None, None, None, None,
            'DEVENGADOS*', None, None, None, None, 'DEVENGADOS*', None, None,
            None, None, 'DEVENGADOS*', None, None, None, None, None, None,
            'DEVENGADOS*', None, None, None, None, 'DEVENGADOS*', None, None,
            'DEVENGADOS*', None, None, 'DEVENGADOS*', None, None,
            'DEVENGADOS*', None, None, 'DEVENGADOS*', None, None,
            'DEVENGADOS*', None, None, None, None, 'DEDUCCIONES*', None, None,
            'DEDUCCIONES*', None, 'DEDUCCIONES*', None, 'DEDUCCIONES*', None,
            'DEDUCCIONES*', None, 'DEDUCCIONES*', None, 'DEDUCCIONES*', None,
            'DEDUCCIONES*', None, 'DEDUCCIONES*', None, None, 'DEDUCCIONES*',
            None, None, 'DEDUCCIONES*', None, 'DEDUCCIONES*', None,
            'DEDUCCIONES*', None, 'DEDUCCIONES*', None, 'DEDUCCIONES*', None,
            'INFORMACIÓN GENERAL*', None, None, None],
           ['TipoNomina*', 'PeriodoNómina*', 'TipoMoneda*',
            'Identificación del  trabajador*', 'Fecha de emisión*',
            'TRM (opcional)', 'Notas (opcional)', 'CUNENov * ', 'númeroPred*',
            'CUNEPred*', 'FechaGenPred*', 'Fecha Ingreso*',
            'Fecha Retiro (opcional)', 'Fecha Inicio Liquidación*',
            'Fecha Fin Liquidación*', 'Tiempo Laborado*', 'Forma de pago*',
            'Metodo de pago*', 'Banco (opcional)', 'Tipo de cuenta (ocional)',
            'número de cuenta (opcional)', 'FechaPago (1:N)',
            'Básico (opcional)', None, 'Transporte (0:N)', None, None, None,
            'Horas Extras y Recargos (opcional)', None, None, None, None, None,
            'Vacaciones (opcional) ', None, None, None, None,
            'Primas (opcional) ', None, None, 'Cesantías (opcional) ', None,
            None, None, 'Incapacidades (opcional) ', None, None, None, None,
            'Licencias (opcional) ', None, None, None, None,
            'Bonificaciones (opcional) ', None, None, 'Auxilios (opcional) ',
            None, None, 'Huelgas Legales (opcional)', None, None,
            'Otros Conceptos (opcional)', None, None,
            'Compensaciones (opcional)', None, None,
            'Bonos Electronicos o de Papel de Servicio, Cheques, Tarjetas, '
            'Vales, etc – EPCTVs (opcional)',
            None, None, None, None, 'Comisiones (opcional)', None,
            'Pagos Terceros (opcional)', None, 'Anticipos (opcional)', None,
            'Otros devengados', None, None, None, None, None, 'Salud*', None,
            None, 'Fondo Pensión*', None, None,
            'Fondo de Seguridad Pensional (opcional)', None, None, None,
            'Sindicatos (opcional)', None, None, None, 'Sanciones (opcional)',
            None, None, 'Libranzas (opcional)', None,
            'Pagos Terceros (opcional)', None, 'Anticipos (opcional)', None,
            'Otras Deducciones (opcional)', None, 'Deducciones Adicionales ',
            None, None, None, None, None, None, None, None, None, None, None,
            None],
           ['Ver código en: Catálogo Tipos de nómina.',
            'Ver código en: Catálogo Periodos de nómina.',
            'Moneda de Colombia', 'Número de documento (9-13 dígitos)',
            'AAAA-MM-DD',
            'Tasa de cambio de la moneda utilizada en el documento en el '
            'Campo “TipoMoneda” a Pesos Colombianos. Valor numérico (0-9 y '
            'punto decimal)',
            'Información adicional: Texto libre, relativo al documento.',
            'Debe ir el CUNE del documento al cual se le realizará la novedad '
            'contractual.',
            'Número de Documento Soporte de Pago de Nómina Electrónica a '
            'Reemplazar.',
            'CUNE del Documento Soporte de Pago de Nómina Electrónica a '
            'Reemplazar.',
            'Fecha de Emision del Documento Soporte de Pago de Nómina '
            'Electrónica a Reemplazar (AAAA-MM-DD)',
            'AAAA-MM-DD', 'AAAA-MM-DD', 'AAAA-MM-DD', 'AAAA-MM-DD',
            'Debe ser mayor o gual a 1. Ver catalogo: Tiempo Laborado.',
            'Se debe colocar el codigo de la tabla: Forma de Pago Ver '
            'Catalogo Pagos .',
            'Se debe colocar el codigo de la tabla: Metodo de Pago Ver '
            'Catalogo Pagos ',
            'Si el método de pago se realiza de forma bancaria.  Se debe '
            'colocar el nombre de la entidad bancaria. Ver Catalogo Bancos',
            'Si el método de pago se realiza de forma bancaria. Se debe '
            'colocar el nombre del tipo de cuenta que el trabajador tiene '
            'para pago de Nómina. Ver Catalogo Tipos Cuenta',
            'Si el método de pago se realiza de forma bancaria. Se debe '
            'colocar el número de la cuenta que el trabajador tiene para pago '
            'de Nómina.',
            'Debe ir la fecha de pago del documento.AAAA-MM-DD',
            'Dias Trabajados*', 'Sueldo Trabajado*',
            'Viaticos : Base (opcional) ', 'Auxilio Transporte (opcional)',
            'Viatico Manual M/A (opcional)',
            'Viatico Manual M/A No salarial (opcional)',
            'Horas Extras y Recargos (0:N)', None, None, None, None, None,
            'Vacaciones (0:N)', None, None, None, None, 'Cantidad*', 'Pago*',
            'PagoNS (opcional)', 'Pago*', 'Porcentaje*', 'Pago Intereses*',
            'Días trabajados*', 'Incapacidad (0:N)', None, None, None, None,
            'Licencia (0:N)', None, None, None, None, 'Bonificacion (0:N)',
            None, None, 'Auxilio (0:N)', None, None, 'Huelga legal (0:N)',
            None, None, 'Otro Concepto (0:N)', None, None,
            'Compensacion (0:N)', None, None,
            'Bono Electronico o de Papel de Servicio, Cheque, Tarjeta, Vale, '
            'etc – EPCTV (0:N)',
            None, None, None, None, 'Comision (0:N)', None,
            'Pago Tercero (0:N)', None, 'Anticipo (0:N)', None,
            'Dotación (opcional)', 'Apoyo Sostenimiento (opcional)',
            'Teletrabajo (opcional)', 'Bonificacion Retiro (opcional)',
            'Indeminización (opcional)', 'Reintegro (opcional)', 'Porcentaje*',
            'Base*', 'Deduccion*', 'Porcentaje*', 'Base*', 'Deduccion*',
            'Porcentaje (opcional)', 'DeduccionSP (opcional)',
            'PorcentajeSub (opcional)', 'DeduccionSub (opcional)',
            'Sindicato (0:N)', None, None, None, 'Sanción (0:N)', None, None,
            'Libranza (0:N)', None, 'PagoTercero (0:N)', None,
            'Anticipo (0:N)', None, 'Otra Deducción (0:N)', None,
            'Pension Voluntaria (opcional)', 'Retencion Fuente (opcional)',
            'AFC (Ahorro Fomento a la contruccion)  (opcional)',
            'Cooperativa (opcional)', 'Embargo Fiscal (opcional)',
            'Planes Complementarios (opcional)', 'Educacion (opcional)',
            'Reintegro (opcional)', 'Deuda (opcional)', 'Redondeo *',
            'Total Devengados *', 'Total Deducciones *',
            'Total Comprobante *'],
           [None, None, None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, None, None,
            'Cantidad de dias laborados durante el Periodo de Pago. Valor '
            'numérico (0-9)',
            'Sueldo Trabajado por los días laborados.Valor numérico (0-9 y '
            'punto decimal)',
            'Base para el cálculo. Valor numérico (0-9). Valor numérico (0-9)',
            'Valor de Auxilio de Transporte que recibe el trabajador por ley, '
            'según aplique. Valor numérico (0-9 y punto decimal)',
            'Valor de Viaticos, Manutención y Alojamiento de carácter '
            'Salarial. Valor numérico (0-9 y punto decimal)',
            'Valor de Viaticos, Manutención y Alojamiento de carácter No '
            'Salarial. Valor numérico (0-9 y punto decimal)',
            'Tipos de horas', 'Hora Inicio', 'Hora Fin', 'Cantidad *',
            'Porcentaje*', 'Pago*', 'Tipo de Vacaciones',
            'Fecha Inicio (opcional)', 'Fecha Fin (opcional)', 'Cantidad*',
            'Pago*', 'Cantidad de dias trabajados. Valor numérico (0-9)',
            'Valor Pagado por Prima Legal con respecto a Cantidad de Dias. '
            'Valor numérico (0-9 y punto decimal)',
            'Valor Pagado por Prima No Salarial. Valor numérico (0-9 y punto '
            'decimal)',
            'Valor Pagado por Cesantias. Valor numérico (0-9 y punto decimal)',
            'Porcentaje de Interes de Cesantias. Valor numérico (0-9)',
            'Valor Pagado por Intereses de Cesantias. Valor numérico (0-9 y '
            'punto decimal)',
            'Cantidad de días trabajados. Valor numérico (0-9)', 'Tipo*',
            'Fecha Inicio*', 'Fecha Fin*', 'Cantidad*', 'Pago*',
            'Tipo de licencia*', 'Fecha Inicio (opcional)',
            'Fecha Fin (opcional)', 'Cantidad*', 'Pago*',
            'Bonificacion Salarial (opcional)',
            'Bonificacion No Salarial (opcional)', 'Descripcion*',
            'Auxilio Salarial (opcional)', 'Auxilio No Salarial (opcional)',
            'Descripción*', 'Fecha Inicio*', 'Fecha Fin*', 'Cantidad*',
            'Descripcion*', 'Concepto Salarial*', 'Concepto No Salarial*',
            'Compensación Ordinaria*', 'Compensación Extraordinaria*',
            'Descripción*', 'Pago Salarial (opcional)',
            'Pago No Salarial (opcional)',
            'Pago Alimentación Salarial (opcional)',
            'Pago Alimentación No Salarial (opcional)', 'Descripción*',
            'Comision*', 'Descripción*', 'PagoTercero', 'Descripción*',
            'Anticipo', 'Descripción*',
            'Valor Pagado por Dotación. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado por Apoyo a Sostenimiento. Valor numérico (0-9 y '
            'punto decimal)',
            'Valor Pagado por trabajo en Teletrabajo. Valor numérico (0-9 y '
            'punto decimal)',
            'Valor Pagado por Retiro de la empresa. Valor numérico (0-9 y '
            'punto decimal)',
            'Valor Pagado por Indemnización. Valor numérico (0-9 y punto '
            'decimal) ',
            'Valor Pagado correspondiente a Reintegro por parte del '
            'empleador. Valor numérico (0-9 y punto decimal)',
            'Se debe colocar el Porcentaje que corresponda a la tabla NOM.7. '
            'Ver Catalogo: Tipo de Deducciones Por Ley',
            'Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Salud por parte del trabajador. '
            'Valor numérico (0-9 y punto decimal)',
            'Se debe colocar el Porcentaje que corresponda a la tabla NOM.7 '
            'Ver Catalogo: Tipo de Deducciones Por Ley',
            'Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Pension por parte del trabajador. '
            'Valor numérico (0-9 y punto decimal)',
            'Se debe colocar el Porcentaje que Corresponda. Valor numérico '
            '(0-9 )',
            'Valor Pagado correspondiente a Fondo de Solidaridad Pensional '
            'por parte del trabajador. Valor numérico (0-9 y punto decimal)',
            'Se debe colocar el Porcentaje que correspondiente al Fondo de '
            'Subsistencia correspondiente. Valor numérico (0-9 )',
            'Valor Pagado correspondiente a Fondo de Subsistencia por parte '
            'del trabajador. Valor numérico (0-9 y punto decimal)',
            'Base*', 'Porcentaje*', 'Deduccion*', 'Descripción*',
            'Sanción Pública', 'Sancion Privada', 'Descripción*',
            'Descripción*', 'Deducción*', 'Pago Tercero*', 'Descripción*',
            'Anticipo*', 'Descripción*', 'Otra Deducción*', 'Descripción*',
            'Valor Pagado correspondiente al ahorro que hace el trabajador '
            'para complementar su pension obligatoria o cumplir metas '
            'especificas. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Retención en la Fuente por parte '
            'del trabajador. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a AFC por parte del trabajador. '
            'Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Cooperativas por parte del '
            'trabajador.Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Embargos Fiscales por parte del '
            'trabajador. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Planes Complementarios por parte '
            'del trabajador. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Conceptos Educativos por parte '
            'del trabajador. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Reintegro por parte del '
            'trabajador. Valor numérico (0-9 y punto decimal)',
            'Valor Pagado correspondiente a Deuda con la Empresa por parte '
            'del trabajador. Valor numérico (0-9 y punto decimal)',
            'Se utiliza para cuando se utilice el Redondeo en el Documento',
            'Valor total de la Suma de todos los Devengados del Documento',
            'Valor total de la Suma de todas las Deducciones del Documento',
            'Debe ir el total de: Devengados - Deducciones'],
           [None, None, None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None,
            'Se debe colocar el codigo del tipo de hora. Ver codigo en: '
            'Catalogo Tipo Horas Extras.',
            'En formato:YYYY-MM-DDTHH:MM:SS',
            'En formato: YYYY-MM-DDTHH:MM:SS',
            'Cantidad de Horas. Valor numérico (0-9)',
            'Ver catalogo: Porcentaje Horas Extras. Valor numérico (0-9).',
            'Valor Pagado por las Horas correspondiente a: (Sueldo /240) x '
            'Porcentaje x Cantidad Valor numérico (0-9 y punto decimal)',
            'Se debe colocar el codigo del tipo de vacacciones. Ver '
            'catalogo:Tipo de Vacaciones.',
            'AAAA-MM-DD  (Aplica solo en Vacaciones Comunes)',
            'AAAA-MM-DD (Aplica solo en Vacaciones Comunes)',
            'Cantidad de Dias. Valor numérico (0-9)',
            'Valor Pagado. Valor numérico (0-9 y punto decimal)', None, None,
            None, None, None, None, None,
            'Ver codigo en catalogo:  Tipo de Incapacidad', 'AAAA-MM-DD ',
            'AAAA-MM-DD', 'Cantidad de Dias Valor numérico (0-9)',
            'Valor Pagado por Incapacidad con respecto a Cantidad de Dias. '
            'Valor numérico (0-9 y punto decimal)',
            'Se debe colocar el codigo de tipos de Licencias. Ver código en '
            'catalgo: Tipo de Licencias',
            'AAAA-MM-DD', 'AAAA-MM-DD',
            'Cantidad de dias Valor numérico (0-9)',
            'Valor Pagado por Licencia. Valor numérico (0-9 y punto decimal)',
            'Valor numérico (0-9 y punto decimal)',
            'Valor numérico (0-9 y punto decimal)',
            'Descripción de la bonificación',
            'Valor numérico (0-9 y punto decimal)',
            'Valor numérico (0-9 y punto decimal)', 'Descripción del auxilio',
            'AAAA-MM-DD', 'AAAA-MM-DD',
            'Cantidad de dias. Valor numérico (0-9)',
            'Debe ir la Descripcion del Concepto',
            'Valor Pagado por Conceptos Salariales. Valor numérico (0-9 y '
            'punto decimal)',
            'Valor Pagado por Conceptos No Salariales. Valor numérico (0-9 y '
            'punto decimal)',
            'Valor Pagado por Compensaciones Ordinarias. Valor numérico (0-9 '
            'y punto decimal)',
            'Valor Pagado por Compensaciones Extraordinarias. Valor numérico '
            '(0-9 y punto decimal)',
            'Descripción de la compensación ',
            'Concepto Salarial. Valor numérico (0-9 y punto decimal)',
            'Concepto No Salarial. Valor numérico (0-9 y punto decimal)',
            'Concepto Salarial. Valor numérico (0-9 y punto decimal)',
            'Concepto No Salarial. Valor numérico (0-9 y punto decimal)',
            'Descripción del bono',
            'Valor Pagado por Comisión. Valor numérico (0-9 y punto decimal)',
            'Descripción de la comisión',
            'Valor Pagado por Pago Tercero. Valor numérico (0-9 y punto '
            'decimal)',
            'Descripción del pago a terceros',
            'Valor Pagado por Anticipo. Valor numérico (0-9 y punto decimal)',
            'Descripción del Anticipo', None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, None,
            'Valor numérico (0-9 y punto decimal)',
            ' Porcentaje que correspondiente a Aportes del Sindicato '
            'correspondiente. Valor numérico (0-9 )',
            'Valor Pagado correspondiente a Aportes del Sindicato por parte '
            'del trabajador. Valor numérico (0-9 y punto decimal)',
            'Descripción del sindicato',
            'Valor numérico (0-9 y punto decimal)',
            'Valor numérico (0-9 y punto decimal)',
            'Descripción de la sanción', 'Descripcion de la Libranza',
            'Valor Pagado correspondiente a Aportes a Entidades Financieras '
            'por parte del trabajador. Valor numérico (0-9 y punto decimal) ',
            'Valor Pagado por Pago Tercero. Valor numérico (0-9 y punto '
            'decimal)',
            'Descripción del pago a tercero',
            'Valor Pagado por Anticipo. Valor numérico (0-9 y punto decimal)',
            'Descripcion del anticipo',
            'Valor Pagado por Otra Deducción.Valor numérico (0-9 y punto '
            'decimal)',
            'Descripción del pago a tercero', None, None, None, None, None,
            None, None, None, None, None, None, None, None]],
 'fills': {'1,1': 'FFFFD060',
           '1,10': 'FFFFD060',
           '1,100': 'FFFFD060',
           '1,101': 'FFFFD060',
           '1,102': 'FFFFD060',
           '1,103': 'FFFFD060',
           '1,104': 'FFFFD060',
           '1,105': 'FFFFD060',
           '1,106': 'FFFFD060',
           '1,107': 'FFFFD060',
           '1,108': 'FFFFD060',
           '1,109': 'FFFFD060',
           '1,11': 'FFFFD060',
           '1,110': 'FFFFD060',
           '1,111': 'FFFFD060',
           '1,112': 'FFFFD060',
           '1,113': 'FFFFD060',
           '1,114': 'FFFFD060',
           '1,115': 'FFFFD060',
           '1,116': 'FFFFD060',
           '1,117': 'FFFFD060',
           '1,118': 'FFFFD060',
           '1,119': 'FFFFD060',
           '1,12': 'FFFFD060',
           '1,120': 'FFFFD060',
           '1,121': 'FFFFD060',
           '1,122': 'FFFFD060',
           '1,123': 'FFFFD060',
           '1,124': 'FFFFD060',
           '1,125': 'FFFFD060',
           '1,126': 'FFFFD060',
           '1,13': 'FFFFD060',
           '1,14': 'FFFFD060',
           '1,15': 'FFFFD060',
           '1,16': 'FFFFD060',
           '1,17': 'FFFFD060',
           '1,18': 'FFFFD060',
           '1,19': 'FFFFD060',
           '1,2': 'FFFFD060',
           '1,20': 'FFFFD060',
           '1,21': 'FFFFD060',
           '1,22': 'FFFFD060',
           '1,23': 'FFFFD060',
           '1,24': 'FFFFD060',
           '1,25': 'FFFFD060',
           '1,26': 'FFFFD060',
           '1,27': 'FFFFD060',
           '1,28': 'FFFFD060',
           '1,29': 'FFFFD060',
           '1,3': 'FFFFD060',
           '1,30': 'FFFFD060',
           '1,31': 'FFFFD060',
           '1,32': 'FFFFD060',
           '1,33': 'FFFFD060',
           '1,34': 'FFFFD060',
           '1,35': 'FFFFD060',
           '1,36': 'FFFFD060',
           '1,37': 'FFFFD060',
           '1,38': 'FFFFD060',
           '1,39': 'FFFFD060',
           '1,4': 'FFFFD060',
           '1,40': 'FFFFD060',
           '1,41': 'FFFFD060',
           '1,42': 'FFFFD060',
           '1,43': 'FFFFD060',
           '1,44': 'FFFFD060',
           '1,45': 'FFFFD060',
           '1,46': 'FFFFD060',
           '1,47': 'FFFFD060',
           '1,48': 'FFFFD060',
           '1,49': 'FFFFD060',
           '1,5': 'FFFFD060',
           '1,50': 'FFFFD060',
           '1,51': 'FFFFD060',
           '1,52': 'FFFFD060',
           '1,53': 'FFFFD060',
           '1,54': 'FFFFD060',
           '1,55': 'FFFFD060',
           '1,56': 'FFFFD060',
           '1,57': 'FFFFD060',
           '1,58': 'FFFFD060',
           '1,59': 'FFFFD060',
           '1,6': 'FFFFD060',
           '1,60': 'FFFFD060',
           '1,61': 'FFFFD060',
           '1,62': 'FFFFD060',
           '1,63': 'FFFFD060',
           '1,64': 'FFFFD060',
           '1,65': 'FFFFD060',
           '1,66': 'FFFFD060',
           '1,67': 'FFFFD060',
           '1,68': 'FFFFD060',
           '1,69': 'FFFFD060',
           '1,7': 'FFFFD060',
           '1,70': 'FFFFD060',
           '1,71': 'FFFFD060',
           '1,72': 'FFFFD060',
           '1,73': 'FFFFD060',
           '1,74': 'FFFFD060',
           '1,75': 'FFFFD060',
           '1,76': 'FFFFD060',
           '1,77': 'FFFFD060',
           '1,78': 'FFFFD060',
           '1,79': 'FFFFD060',
           '1,8': 'FFFFD060',
           '1,80': 'FFFFD060',
           '1,81': 'FFFFD060',
           '1,82': 'FFFFD060',
           '1,83': 'FFFFD060',
           '1,84': 'FFFFD060',
           '1,85': 'FFFFD060',
           '1,86': 'FFFFD060',
           '1,87': 'FFFFD060',
           '1,88': 'FFFFD060',
           '1,89': 'FFFFD060',
           '1,9': 'FFFFD060',
           '1,90': 'FFFFD060',
           '1,91': 'FFFFD060',
           '1,92': 'FFFFD060',
           '1,93': 'FFFFD060',
           '1,94': 'FFFFD060',
           '1,95': 'FFFFD060',
           '1,96': 'FFFFD060',
           '1,97': 'FFFFD060',
           '1,98': 'FFFFD060',
           '1,99': 'FFFFD060',
           '2,1': 'FFBD3B5D',
           '2,100': 'FF062A51',
           '2,101': 'FF062A51',
           '2,102': 'FF062A51',
           '2,103': 'FF062A51',
           '2,104': 'FF062A51',
           '2,105': 'FF062A51',
           '2,106': 'FF062A51',
           '2,107': 'FF062A51',
           '2,108': 'FF062A51',
           '2,110': 'FF062A51',
           '2,111': 'FF062A51',
           '2,112': 'FF062A51',
           '2,113': 'FF062A51',
           '2,114': 'FF062A51',
           '2,115': 'FF062A51',
           '2,116': 'FF062A51',
           '2,117': 'FF062A51',
           '2,118': 'FF062A51',
           '2,119': 'FF062A51',
           '2,12': 'FF062A51',
           '2,120': 'FF062A51',
           '2,121': 'FF062A51',
           '2,122': 'FF062A51',
           '2,123': 'FFBD3B5D',
           '2,17': 'FFBD3B5D',
           '2,18': 'FFBD3B5D',
           '2,19': 'FFBD3B5D',
           '2,20': 'FFBD3B5D',
           '2,21': 'FFBD3B5D',
           '2,22': 'FF062A51',
           '2,23': 'FFBD3B5D',
           '2,24': 'FFBD3B5D',
           '2,25': 'FFBD3B5D',
           '2,26': 'FFBD3B5D',
           '2,27': 'FFBD3B5D',
           '2,28': 'FFBD3B5D',
           '2,29': 'FFBD3B5D',
           '2,30': 'FFBD3B5D',
           '2,31': 'FFBD3B5D',
           '2,32': 'FFBD3B5D',
           '2,33': 'FFBD3B5D',
           '2,34': 'FFBD3B5D',
           '2,35': 'FFBD3B5D',
           '2,36': 'FFBD3B5D',
           '2,37': 'FFBD3B5D',
           '2,38': 'FFBD3B5D',
           '2,39': 'FFBD3B5D',
           '2,40': 'FFBD3B5D',
           '2,41': 'FFBD3B5D',
           '2,42': 'FFBD3B5D',
           '2,43': 'FFBD3B5D',
           '2,44': 'FFBD3B5D',
           '2,45': 'FFBD3B5D',
           '2,46': 'FFBD3B5D',
           '2,47': 'FFBD3B5D',
           '2,48': 'FFBD3B5D',
           '2,49': 'FFBD3B5D',
           '2,50': 'FFBD3B5D',
           '2,51': 'FFBD3B5D',
           '2,52': 'FFBD3B5D',
           '2,53': 'FFBD3B5D',
           '2,54': 'FFBD3B5D',
           '2,55': 'FFBD3B5D',
           '2,56': 'FFBD3B5D',
           '2,57': 'FFBD3B5D',
           '2,58': 'FFBD3B5D',
           '2,59': 'FFBD3B5D',
           '2,60': 'FFBD3B5D',
           '2,61': 'FFBD3B5D',
           '2,62': 'FFBD3B5D',
           '2,63': 'FFBD3B5D',
           '2,64': 'FFBD3B5D',
           '2,65': 'FFBD3B5D',
           '2,66': 'FFBD3B5D',
           '2,67': 'FFBD3B5D',
           '2,68': 'FFBD3B5D',
           '2,69': 'FFBD3B5D',
           '2,70': 'FFBD3B5D',
           '2,71': 'FFBD3B5D',
           '2,72': 'FFBD3B5D',
           '2,73': 'FFBD3B5D',
           '2,74': 'FFBD3B5D',
           '2,75': 'FFBD3B5D',
           '2,76': 'FFBD3B5D',
           '2,77': 'FFBD3B5D',
           '2,78': 'FFBD3B5D',
           '2,79': 'FFBD3B5D',
           '2,8': 'FF062A51',
           '2,80': 'FFBD3B5D',
           '2,81': 'FFBD3B5D',
           '2,82': 'FFBD3B5D',
           '2,83': 'FFBD3B5D',
           '2,84': 'FFBD3B5D',
           '2,85': 'FFBD3B5D',
           '2,86': 'FFBD3B5D',
           '2,87': 'FFBD3B5D',
           '2,88': 'FFBD3B5D',
           '2,89': 'FF062A51',
           '2,9': 'FFBD3B5D',
           '2,90': 'FF062A51',
           '2,91': 'FF062A51',
           '2,92': 'FF062A51',
           '2,93': 'FF062A51',
           '2,94': 'FF062A51',
           '2,95': 'FF062A51',
           '2,96': 'FF062A51',
           '2,97': 'FF062A51',
           '2,98': 'FF062A51',
           '2,99': 'FF062A51',
           '3,1': 'FFBD3B5D',
           '3,10': 'FFBD3B5D',
           '3,103': 'FF062A51',
           '3,106': 'FF062A51',
           '3,108': 'FF062A51',
           '3,11': 'FFBD3B5D',
           '3,110': 'FF062A51',
           '3,112': 'FF062A51',
           '3,114': 'FF062A51',
           '3,12': 'FF062A51',
           '3,123': 'FFBD3B5D',
           '3,124': 'FFBD3B5D',
           '3,125': 'FFBD3B5D',
           '3,126': 'FFBD3B5D',
           '3,13': 'FF062A51',
           '3,14': 'FF062A51',
           '3,15': 'FF062A51',
           '3,16': 'FF062A51',
           '3,17': 'FFBD3B5D',
           '3,18': 'FFBD3B5D',
           '3,19': 'FFBD3B5D',
           '3,2': 'FFBD3B5D',
           '3,20': 'FFBD3B5D',
           '3,21': 'FFBD3B5D',
           '3,22': 'FF062A51',
           '3,23': 'FFBD3B5D',
           '3,25': 'FFBD3B5D',
           '3,29': 'FFBD3B5D',
           '3,3': 'FFBD3B5D',
           '3,35': 'FFBD3B5D',
           '3,4': 'FFBD3B5D',
           '3,40': 'FFBD3B5D',
           '3,43': 'FFBD3B5D',
           '3,46': 'FFBD3B5D',
           '3,47': 'FFBD3B5D',
           '3,5': 'FFBD3B5D',
           '3,52': 'FFBD3B5D',
           '3,57': 'FFBD3B5D',
           '3,6': 'FFBD3B5D',
           '3,60': 'FFBD3B5D',
           '3,63': 'FFBD3B5D',
           '3,66': 'FFBD3B5D',
           '3,69': 'FFBD3B5D',
           '3,7': 'FFBD3B5D',
           '3,72': 'FFBD3B5D',
           '3,77': 'FFBD3B5D',
           '3,79': 'FFBD3B5D',
           '3,8': 'FF062A51',
           '3,81': 'FFBD3B5D',
           '3,83': 'FFBD3B5D',
           '3,89': 'FF062A51',
           '3,9': 'FFBD3B5D',
           '3,92': 'FF062A51',
           '3,95': 'FF062A51',
           '3,99': 'FF062A51',
           '4,1': 'FFF8FAFC',
           '4,10': 'FFF3F3F3',
           '4,103': 'FF062A51',
           '4,106': 'FF062A51',
           '4,108': 'FF062A51',
           '4,11': 'FFF3F3F3',
           '4,110': 'FF062A51',
           '4,112': 'FF062A51',
           '4,114': 'FF062A51',
           '4,115': 'FF062A51',
           '4,116': 'FF062A51',
           '4,117': 'FF062A51',
           '4,118': 'FF062A51',
           '4,119': 'FF062A51',
           '4,12': 'FFF8FAFC',
           '4,120': 'FF062A51',
           '4,121': 'FF062A51',
           '4,122': 'FF062A51',
           '4,123': 'FFBD3B5D',
           '4,124': 'FFBD3B5D',
           '4,125': 'FFBD3B5D',
           '4,126': 'FFBD3B5D',
           '4,13': 'FFF8FAFC',
           '4,14': 'FFF8FAFC',
           '4,15': 'FFF8FAFC',
           '4,16': 'FFF8FAFC',
           '4,17': 'FFF3F3F3',
           '4,18': 'FFF3F3F3',
           '4,19': 'FFF3F3F3',
           '4,2': 'FFF8FAFC',
           '4,20': 'FFF3F3F3',
           '4,21': 'FFF3F3F3',
           '4,22': 'FFF8FAFC',
           '4,23': 'FF002751',
           '4,24': 'FF002751',
           '4,25': 'FFFFD060',
           '4,26': 'FFFFD060',
           '4,27': 'FFFFD060',
           '4,28': 'FFFFD060',
           '4,29': 'FFBD3B5D',
           '4,3': 'FFF8FAFC',
           '4,35': 'FFBD3B5D',
           '4,4': 'FFF8FAFC',
           '4,40': 'FF002751',
           '4,41': 'FF062A51',
           '4,42': 'FF062A51',
           '4,43': 'FFFFD060',
           '4,44': 'FFFFD060',
           '4,45': 'FFFFD060',
           '4,46': 'FFFFD060',
           '4,47': 'FFBD3B5D',
           '4,5': 'FFF8FAFC',
           '4,52': 'FFBD3B5D',
           '4,57': 'FFBD3B5D',
           '4,6': 'FFF8FAFC',
           '4,60': 'FFBD3B5D',
           '4,63': 'FFBD3B5D',
           '4,66': 'FFBD3B5D',
           '4,69': 'FFBD3B5D',
           '4,7': 'FFF8FAFC',
           '4,72': 'FFBD3B5D',
           '4,77': 'FFBD3B5D',
           '4,79': 'FFBD3B5D',
           '4,8': 'FFF3F3F3',
           '4,81': 'FFBD3B5D',
           '4,83': 'FFBD3B5D',
           '4,84': 'FFBD3B5D',
           '4,85': 'FFBD3B5D',
           '4,86': 'FFBD3B5D',
           '4,87': 'FFBD3B5D',
           '4,88': 'FFBD3B5D',
           '4,89': 'FFFFD060',
           '4,9': 'FFF3F3F3',
           '4,90': 'FFFFD060',
           '4,91': 'FFFFD060',
           '4,92': 'FF062A51',
           '4,93': 'FF062A51',
           '4,94': 'FF062A51',
           '4,95': 'FFFFD060',
           '4,96': 'FFFFD060',
           '4,97': 'FFFFD060',
           '4,98': 'FFFFD060',
           '4,99': 'FF062A51',
           '5,100': 'FF002751',
           '5,101': 'FF002751',
           '5,102': 'FF002751',
           '5,103': 'FFFFD060',
           '5,104': 'FFFFD060',
           '5,105': 'FFFFD060',
           '5,106': 'FF002751',
           '5,107': 'FF002751',
           '5,108': 'FFFFD060',
           '5,109': 'FFFFD060',
           '5,110': 'FF062A51',
           '5,111': 'FF002751',
           '5,112': 'FFFFD060',
           '5,113': 'FFFFD060',
           '5,114': 'FFF8FAFC',
           '5,115': 'FFF3F3F3',
           '5,116': 'FFF8FAFC',
           '5,117': 'FFF3F3F3',
           '5,118': 'FFF8FAFC',
           '5,119': 'FFF3F3F3',
           '5,120': 'FFF8FAFC',
           '5,121': 'FFF3F3F3',
           '5,122': 'FFF8FAFC',
           '5,123': 'FFF8FAFC',
           '5,124': 'FFF8FAFC',
           '5,125': 'FFF8FAFC',
           '5,126': 'FFF8FAFC',
           '5,23': 'FFF3F3F3',
           '5,24': 'FFF3F3F3',
           '5,25': 'FFF8FAFC',
           '5,26': 'FFF8FAFC',
           '5,27': 'FFF8FAFC',
           '5,28': 'FFF8FAFC',
           '5,29': 'FF062A51',
           '5,30': 'FF062A51',
           '5,31': 'FF062A51',
           '5,32': 'FF062A51',
           '5,33': 'FF062A51',
           '5,34': 'FF062A51',
           '5,35': 'FFFFD060',
           '5,36': 'FFFFD060',
           '5,37': 'FFFFD060',
           '5,38': 'FFFFD060',
           '5,39': 'FFFFD060',
           '5,40': 'FFF3F3F3',
           '5,41': 'FFF3F3F3',
           '5,42': 'FFF3F3F3',
           '5,43': 'FFF8FAFC',
           '5,44': 'FFF8FAFC',
           '5,45': 'FFF8FAFC',
           '5,46': 'FFF8FAFC',
           '5,47': 'FF062A51',
           '5,48': 'FF062A51',
           '5,49': 'FF062A51',
           '5,50': 'FF062A51',
           '5,51': 'FF062A51',
           '5,52': 'FFFFD060',
           '5,53': 'FFFFD060',
           '5,54': 'FFFFD060',
           '5,55': 'FFFFD060',
           '5,56': 'FFFFD060',
           '5,57': 'FF062A51',
           '5,58': 'FF062A51',
           '5,59': 'FF062A51',
           '5,60': 'FFFFD060',
           '5,61': 'FFFFD060',
           '5,62': 'FFFFD060',
           '5,63': 'FF062A51',
           '5,64': 'FF062A51',
           '5,65': 'FF062A51',
           '5,66': 'FFFFD060',
           '5,67': 'FFFFD060',
           '5,68': 'FFFFD060',
           '5,69': 'FF062A51',
           '5,70': 'FF062A51',
           '5,71': 'FF062A51',
           '5,72': 'FFFFD060',
           '5,73': 'FFFFD060',
           '5,74': 'FFFFD060',
           '5,75': 'FFFFD060',
           '5,76': 'FFFFD060',
           '5,77': 'FF062A51',
           '5,78': 'FF062A51',
           '5,79': 'FFFFD060',
           '5,80': 'FFFFD060',
           '5,81': 'FF062A51',
           '5,82': 'FF062A51',
           '5,83': 'FFF8FAFC',
           '5,84': 'FFF8FAFC',
           '5,85': 'FFF8FAFC',
           '5,86': 'FFF8FAFC',
           '5,87': 'FFF8FAFC',
           '5,88': 'FFF8FAFC',
           '5,89': 'FFF3F3F3',
           '5,90': 'FFF3F3F3',
           '5,91': 'FFF3F3F3',
           '5,92': 'FFF8FAFC',
           '5,93': 'FFF8FAFC',
           '5,94': 'FFF8FAFC',
           '5,95': 'FFF3F3F3',
           '5,96': 'FFF3F3F3',
           '5,97': 'FFF3F3F3',
           '5,98': 'FFF3F3F3',
           '5,99': 'FF002751',
           '6,100': 'FFF8FAFC',
           '6,101': 'FFF8FAFC',
           '6,102': 'FFF8FAFC',
           '6,103': 'FFF3F3F3',
           '6,104': 'FFF3F3F3',
           '6,105': 'FFF3F3F3',
           '6,106': 'FFF8FAFC',
           '6,107': 'FFF8FAFC',
           '6,108': 'FFF3F3F3',
           '6,109': 'FFF3F3F3',
           '6,110': 'FFF8FAFC',
           '6,111': 'FFF8FAFC',
           '6,112': 'FFF3F3F3',
           '6,113': 'FFF3F3F3',
           '6,29': 'FFF3F3F3',
           '6,30': 'FFF3F3F3',
           '6,31': 'FFF3F3F3',
           '6,32': 'FFF3F3F3',
           '6,33': 'FFF3F3F3',
           '6,34': 'FFF3F3F3',
           '6,35': 'FFF8FAFC',
           '6,36': 'FFF8FAFC',
           '6,37': 'FFF8FAFC',
           '6,38': 'FFF8FAFC',
           '6,39': 'FFF8FAFC',
           '6,47': 'FFF3F3F3',
           '6,48': 'FFF3F3F3',
           '6,49': 'FFF3F3F3',
           '6,50': 'FFF3F3F3',
           '6,51': 'FFF3F3F3',
           '6,52': 'FFF8FAFC',
           '6,53': 'FFF8FAFC',
           '6,54': 'FFF8FAFC',
           '6,55': 'FFF8FAFC',
           '6,56': 'FFF8FAFC',
           '6,57': 'FFF3F3F3',
           '6,58': 'FFF3F3F3',
           '6,59': 'FFF3F3F3',
           '6,60': 'FFF8FAFC',
           '6,61': 'FFF8FAFC',
           '6,62': 'FFF3F3F3',
           '6,63': 'FFF3F3F3',
           '6,64': 'FFF3F3F3',
           '6,65': 'FFF3F3F3',
           '6,66': 'FFF8FAFC',
           '6,67': 'FFF8FAFC',
           '6,68': 'FFF8FAFC',
           '6,69': 'FFF3F3F3',
           '6,70': 'FFF3F3F3',
           '6,71': 'FFF3F3F3',
           '6,72': 'FFF8FAFC',
           '6,73': 'FFF8FAFC',
           '6,74': 'FFF8FAFC',
           '6,75': 'FFF8FAFC',
           '6,76': 'FFF8FAFC',
           '6,77': 'FFF3F3F3',
           '6,78': 'FFF3F3F3',
           '6,79': 'FFF8FAFC',
           '6,80': 'FFF8FAFC',
           '6,81': 'FFF3F3F3',
           '6,82': 'FFF3F3F3',
           '6,99': 'FFF8FAFC'},
 'merges': ['AN5:AN6', 'BY4:BZ4', 'AP5:AP6', 'DS2:DV2', 'CA4:CB4', 'CP5:CP6',
            'DJ3:DR3', 'CR5:CR6', 'BK4:BM4', 'AT5:AT6', 'AU4:AY4', 'K4:K6',
            'DM5:DM6', 'M4:M6', 'DH3:DI3', 'DJ5:DJ6', 'W3:X3', 'CU4:CX4',
            'DD2:DE2', 'N4:N6', 'DP5:DP6', 'P4:P6', 'DB3:DC3', 'CL5:CL6',
            'V4:V6', 'AZ3:BD3', 'I2:K2', 'CI5:CI6', 'AS5:AS6', 'CK5:CK6',
            'D4:D6', 'DD4:DE4', 'CU3:CX3', 'G4:G6', 'A4:A6', 'BQ3:BS3',
            'BY3:BZ3', 'S4:S6', 'DS5:DS6', 'DU5:DU6', 'U4:U6', 'DR5:DR6',
            'X5:X6', 'Z5:Z6', 'CQ5:CQ6', 'AI4:AM4', 'CN5:CN6', 'AN3:AP3',
            'DF3:DG3', 'BH3:BJ3', 'J4:J6', 'DL5:DL6', 'L4:L6', 'W5:W6',
            'Y5:Y6', 'I4:I6', 'AA5:AA6', 'BK3:BM3', 'BN4:BP4', 'CT5:CT6',
            'CE5:CE6', 'AO5:AO6', 'CG5:CG6', 'AQ5:AQ6', 'CS5:CS6', 'Y3:AB3',
            'CK3:CM3', 'AR5:AR6', 'CC4:CD4', 'DK5:DK6', 'CQ3:CT3', 'CY3:DA3',
            'C4:C6', 'AI3:AM3', 'DO5:DO6', 'O4:O6', 'DQ5:DQ6', 'Q4:Q6',
            'AU3:AY3', 'A2:G2', 'CF5:CF6', 'DN5:DN6', 'AC3:AH3', 'CE3:CJ3',
            'CM5:CM6', 'BN3:BP3', 'BQ4:BS4', 'CY4:DA4', 'L2:P2', 'CJ5:CJ6',
            'DD3:DE3', 'AC4:AH4', 'CH5:CH6', 'CN3:CP3', 'B4:B6', 'DB4:DC4',
            'F4:F6', 'H4:H6', 'AZ4:BD4', 'BT3:BX3', 'R4:R6', 'DT5:DT6',
            'T4:T6', 'DF4:DG4', 'DV5:DV6', 'DH4:DI4', 'E4:E6', 'BE3:BG3',
            'BH4:BJ4', 'CA3:CB3', 'CC3:CD3', 'BT4:BX4', 'CO5:CO6', 'AB5:AB6',
            'BE4:BG4', 'AQ3:AS3']}


# v6.11.1: layout de carga de la firma (LayoutNominaCargaMasiva, EMPRESA G
# oct-2026) vacio desde la fila 7, tal cual: encabezado, colores, letras,
# combinadas y anchos. La fila 7 conserva el formato de una fila de datos
# (fechas, numeros) y sirve de modelo para cada empleado.
LAYOUT_NE_B64 = (
    "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"
)
