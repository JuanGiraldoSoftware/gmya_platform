# GMYA Tools v6.23 · Proyecto modular

Plataforma de automatización contable de Giraldo Mosquera y Asociados SAS.

> Versión pública: los nombres de clientes aparecen como «EMPRESA A», «EMPRESA B»…, con NIT y
> ejemplos ficticios. Los datos de clientes (empleados, terceros, documentos y casos de prueba) no
> forman parte de este repositorio.
Desde la v6.3 el código ya no está en un solo archivo (`gmyatools_v2.py`):
está dividido en el paquete `gmya/`. **El funcionamiento es el mismo**, y el
ejecutable, el .zip y la carpeta de instalación se siguen llamando igual
(`GMYA_tools_v2.exe`, `GMYA_tools_v2_<versión>.zip`, `C:\GMYA_tools_v2\`).

---

## 1. Dónde poner el proyecto

1. Descomprime este .zip en una carpeta **nueva**. Recomendado, una ruta corta
   sin espacios ni tildes:

   ```
   C:\GMYA\proyecto_tools\
   ```

   (Puedes usar tu carpeta actual `...\dashboard_txt_empleados\`, pero es mejor
   empezar limpio para no mezclar el `gmyatools_v2.py` viejo con el nuevo).
2. Copia en esa carpeta tu **`gmya.ico`** original (el que usabas para
   compilar). El .zip trae uno generado desde el ícono incrustado; si tienes el
   original, reemplázalo.
3. Si tenías carpeta `assets\` (logos), cópiala también. Es opcional.

La carpeta debe quedar así:

```
C:\GMYA\proyecto_tools\
├─ compilar_firmar_empaquetar.ps1   ← lo único que ejecutas para una versión
├─ run_gmyatools.py                 ← lanzador (entrada del .exe)
├─ app.py                           ← la app de Streamlit (menú y pantallas)
├─ requirements.txt
├─ gmya.ico
├─ README.md
├─ pruebas\verificar.py             ← verificaciones antes de compilar
├─ pruebas\regresion.py             ← motor de regresión (los casos reales van fuera del repo, v6.23)
└─ gmya\                            ← todo el código, por módulos
   ├─ config.py                     ← VERSION y recursos
   ├─ comun\                        ← texto, números, fechas, lectura Excel/XLS/PDF, caché
   ├─ ui\                           ← estilos, componentes, globos, visor
   ├─ registro\                     ← usuario del equipo y registro de uso
   └─ modulos\
      ├─ inicio.py                  ← menú (MODULOS) e Inicio
      ├─ planillas\  bancos\  dian\  busqueda\  pagos\  odoo\  nomina\  terceros\  facturas\
      │    cada uno con logica*.py (sin Streamlit) e interfaz.py (pantalla)
```

## 2. Primera vez (una sola vez por computador de compilación)

Abre **PowerShell** (no la terminal de VS Code con otro Python) y párate en la
carpeta del proyecto:

```powershell
cd C:\GMYA\proyecto_tools
```

Recomendado: crea un entorno virtual dentro de la carpeta. El script lo
detecta solo (`.venv\Scripts\python.exe`):

```powershell
py -m venv .venv
```

Si PowerShell no deja ejecutar scripts, permítelo solo para tu usuario (una
vez):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

El certificado de firma (huella `<HUELLA_DEL_CERTIFICADO>`)
debe estar en *Certificados - Usuario actual > Personal*, como antes.

## 3. Generar una versión nueva (lo de siempre)

En la **misma ventana de PowerShell**, dentro de la carpeta del proyecto:

```powershell
.\compilar_firmar_empaquetar.ps1
```

**No cierres la consola** mientras corre (tarda unos minutos). Hace en orden:

| Paso | Qué hace |
|---|---|
| 1 | Usa `.venv` si existe; si no, el `python` del sistema |
| 2 | Instala `requirements.txt` + PyInstaller |
| 3 | Comprueba que importen streamlit, pdfplumber, openpyxl, pypdfium2, Pillow, **xlrd** y pandas |
| 4 | Revisa que estén `run_gmyatools.py`, `app.py`, `gmya\` y `gmya.ico` |
| 5 | Corre `python -m pruebas.verificar`. **Si falla, no compila** |
| 6 | PyInstaller → `dist_tools_v2\GMYA_tools_v2\GMYA_tools_v2.exe` |
| 7 | Firma el .exe (debe quedar *Valid*) |
| 8 | Crea `GMYA_tools_v2_<VERSION>_AAAAMMDD.zip` en la carpeta del proyecto |

Al final verás **LISTO** en verde con la ruta del .zip. Ese .zip es el que se
instala en los equipos.

Opciones:

```powershell
.\compilar_firmar_empaquetar.ps1 -Version v6.3     # nombre del zip a mano
.\compilar_firmar_empaquetar.ps1 -SinPruebas       # no recomendado
```

## 4. Instalar en los equipos (sin cambios)

Descomprimir el .zip **encima** de `C:\GMYA_tools_v2\` conservando
`config_gmya.txt` y `GMYA_publico.cer`. El acceso directo, el puerto (8502),
`GMYA_NO_BROWSER` y `GMYA_PORT` funcionan igual.

## 5. Probar sin compilar (desarrollo)

Con la consola en la carpeta del proyecto (y el `.venv` activado si lo usas:
`.\.venv\Scripts\Activate.ps1`):

```powershell
streamlit run app.py          # o:
python run_gmyatools.py       # exactamente como arranca el .exe
python -m pruebas.verificar   # solo las verificaciones
python -m pruebas.regresion C:\ruta\datos   # regresión con documentos reales
```

## 6. Cómo cambiar cosas

- **Versión**: edita `VERSION` en `gmya\config.py`. El pie de página, el
  registro de uso y el nombre del .zip la toman de ahí.
- **Regla de un módulo**: está en `gmya\modulos\<módulo>\logica*.py`; la
  pantalla en `interfaz.py`. Cada archivo empieza con su **contrato** (qué
  recibe, qué devuelve y qué reglas no se pueden romper).
- **Módulo nuevo**: crear `gmya\modulos\<nuevo>\` (logica + interfaz),
  agregarlo a `MODULOS` e `ICONOS_MODULO` en `gmya\modulos\inicio.py` y a
  `PANTALLAS` en `app.py`. `pruebas\verificar.py` avisa si falta.
- **Reportar un error**: no es un módulo del menú; es el botón de la barra
  superior (`_barra_superior` en `app.py`, estilo `.gm-marca-barra` en
  `gmya\ui\estilos.py`). Su pantalla está en `gmya\modulos\reporte\` y en
  `PANTALLAS_FUERA_DEL_MENU` de `inicio.py`.
- **Programación de pagos – empresas tipo «cuentas por pagar»** (EMPRESA D, EMPRESA F): `gmya\modulos\pagos\empresa_d.py`
  es el motor común. Cada empresa se configura en `EMPRESAS_PROG_PAGOS` (`pagos\lectura.py`);
  EMPRESA F tiene `variantes` (cuentas por pagar / por cobrar) con sus reglas (tipos y terceros que
  van fuera del listado, texto de vencida, títulos).
- **Datos privados de clientes** (v6.23, `gmya\registro\privados.py`): empleados, beneficiarios, cargos y
  terceros de los clientes **no van en el código** (el repositorio puede ser público). Se guardan como JSON en
  la carpeta «GMYA Tools» (o en `~\.gmya` si no hay carpeta) con `leer_privado` / `guardar_privado`:
  `odoo_maestro.json` (relación de cuentas y centros de costo; se importa desde el Excel de la empresa en el
  módulo Odoo), `odoo_coberturas.json` (beneficiarios al 100 %), `facturacion_cargos.json` (cargos de
  quienes no están en la lista de tarifas; botón «Guardar cargos») y `empresa_b_config.json` (terceros por fuera
  del flujo y anticipos agrupados por mes). Los casos de regresión con documentos reales y sus resultados
  esperados están en `CARPETA_DE_DATOS\casos_privados.py` (lista `CASOS`), que `pruebas\regresion.py` carga.
  `.gitignore` excluye datos, Excel, PDF, JSON, ZIP, registros y certificados. **Regla**: ningún nombre,
  cédula, cuenta bancaria, número de factura ni cifra de un cliente en código, comentarios ni ayudas.
- **Renombrar facturas** (v6.22, módulo 8, `gmya\modulos\facturas\`): `logica.py` lee PDF (texto), XML de la
  DIAN (Invoice, CreditNote, AttachedDocument) y ZIP; el nombre es «PROVEEDOR NÚMERO» con el tercero que no
  es la propia empresa (NIT más frecuente de la carpeta). Número validado con el rango de la resolución y NIT
  con su dígito de verificación. Conserva «codigo …» del nombre original. Carpeta del equipo (copiar a otra
  carpeta o renombrar en el sitio) o archivos subidos (ZIP), siempre con REGISTRO. Nunca escribe dentro de
  «001. EMPRESAS ACTIVAS USO DIARIO» (`protegida`). Nombres corregidos se recuerdan por NIT en
  `facturas_proveedores.json` (carpeta GMYA Tools).
- **Facturación por horas EMPRESA A** (v6.21, opción de Pagos de nómina): `gmya\modulos\nomina\facturacion.py`.
  Lee el libro de nómina y costos (hojas «Nomina <mes>» e «INGRESOS Y RETIROS») y el resumen de tarifas
  («Tarifa Colaborador»); por mes, horas = días pagados (PILA) ÷ 30 × 168 (o ÷ 5 × 42) con tope 168 y
  valor = horas × (mínima + factor × (máxima − mínima)), solo las BU elegidas (BU1). Empleados sin tarifa
  toman la de su cargo (`facturacion_cargos.json`, v6.23). Excel con fórmulas vivas (PARAMETROS y TARIFAS editables).
- **Creación de terceros** (v6.20, módulo 7, `gmya\modulos\terceros\`): `logica.py` lee el listado de
  clientes de HELISA, los contactos de Alegra (.zip con CSV, partes sin títulos incluidas) y el reporte de
  facturación de Medifony, y opcionalmente el resultado de la Consulta de Cédulas; cruza por documento
  normalizado (sin caracteres invisibles ni ceros a la izquierda) y arma el Excel con la hoja «A SUBIR A
  HELISA» en el formato de la firma (`COLUMNAS_SUBIR`). Clases de HELISA por tipo de documento en
  `CLASES_HELISA` (editables en pantalla); valores fijos (CARTERA, NATURALEZA, REGIMEN, RESPONSABLE) en
  `CONFIG_TERCEROS`. Corrección general: `tabla_desde_archivo` (`comun\grilla.py`) ya no confunde la hoja
  BIFF suelta de HELISA con un texto.
- **Revisión de movimientos del banco** (v6.19, dentro de Conciliación bancaria): el archivo de
  movimientos de Bancolombia tal como se descarga (CSV sin títulos ni saldos) se lee con
  `leer_movimientos_sin_encabezado` (`bancos\conciliacion.py`). Al cruzar, a igual valor se prefiere el
  mismo tercero (`mismo_tercero`), un movimiento del banco puede ser varias líneas de HELISA del mismo
  tercero, y cada pareja se revisa (`revisar_terceros`: tercero distinto, días entre fechas). Además del
  Excel de conciliación sale la **revisión en el formato de la firma** (`bancos\revision.py`): el
  archivo del banco pintado (verde correcto, rosado ingresos, amarillo gastos bancarios, naranja no está
  en HELISA) con DOCUMENTO HELISA, REVISIONES y hoja RESUMEN. Saldo inicial del banco opcional en
  Opciones avanzadas; en cortes parciales lo de HELISA posterior al último día del banco no es pendiente.
- **Flujo de caja EMPRESA B** (v6.18, empresa «EMPRESA B», formato `empresa_b` en Programación de pagos):
  `gmya\modulos\pagos\empresa_b.py`. Lee el flujo de caja anterior y la relación de anticipos anterior
  y los cruza con cuatro informes de HELISA (cartera, cuentas por pagar, anticipos realizados,
  anticipos recibidos; se reconocen solos). Semanas de lunes a domingo con dos cuentas (Davivienda
  y Bold); el saldo inicial es el proyectado de la última semana pasada (editable). Cruce por
  número de documento, luego tercero + fecha + valor; lo proyectado en semanas pasadas que sigue
  pendiente se avisa y queda sin semana; documentos nuevos por fecha de vencimiento; pagos fijos
  pagados se corren al mes siguiente. La relación de anticipos solo deja lo que HELISA trae por
  aplicar y su total debe ser igual al de HELISA. Filas permanentes en `CONFIG_EMPRESA_B`; terceros fuera
  del flujo y anticipos por mes en `empresa_b_config.json` (v6.23). Salen dos Excel con el formato y las fórmulas de los anteriores.
- **Programación de pagos EMPRESA E** (v6.11, cuentas por pagar y por cobrar con el formato propio de EMPRESA E):
  `gmya\modulos\pagos\empresa_e.py` (lectura de la programación anterior, armado y Excel).
- **Conciliación de nómina** (opción de Pagos de nómina): `gmya\modulos\nomina\conciliacion.py`.
- **Nómina electrónica** (v6.11, opción de Pagos de nómina): `gmya\modulos\nomina\electronica.py`
  arma la plantilla de carga DIAN desde el acumulado por concepto y periodo + el movimiento de
  prueba de HELISA; el encabezado de la plantilla está en `nomina\plantilla_ne.py`.
  Desde v6.11.1 acepta los archivos originales de HELISA y entrega dos Excel: el archivo plano
  para subir (layout de carga, solo valores) y el Excel de control.
  Desde v6.11.2 el layout de la firma va incrustado tal cual (`LAYOUT_NE_B64` en
  `plantilla_ne.py`): para cambiar el formato, reemplazar ese layout vacío.
- **Diseño** (v6.12): sistema de diseño en `gmya\ui\estilos.py`. Los colores, radios y sombras
  son variables (`--gm-m-*` magenta de la marca, `--gm-n-*` neutros, estados `--gm-ok/alerta/error`);
  no escribir colores sueltos en los módulos, usar las variables. Una sola tipografía (Inter).
  El tema de los controles nativos (radio, casillas, foco) está en `.streamlit\config.toml` y, para el
  .exe, en `TEMA` de `run_gmyatools.py` (mismo color: #C20C7B). Los componentes con su propio HTML
  (visor en `gmya\ui\visor.py`, explorador en `busqueda\logica.py`, globos en `gmya\ui\globos.py`)
  usan la misma paleta. Las tarjetas de Inicio salen de `_TARJETAS_INICIO` en `inicio.py`.
- **Tema oscuro** (v6.15): todo el tablero es oscuro. Los tokens de `estilos.py` conservan sus
  nombres pero la escala va de oscuro a claro (`--gm-n-0` superficie de tarjetas, `--gm-n-50` fondo,
  `--gm-n-900` texto); `--gm-m-txt` es el magenta para texto sobre fondo oscuro. Streamlit corre con
  `base = "dark"` (`.streamlit\config.toml`, `TEMA` de `run_gmyatools.py` y el relanzamiento de
  `app.py`). Encabezado de módulo de v6.11 (degradado carbón → magenta con el logo). En el menú, el
  módulo actual se sombrea como un todo (nada dentro del botón lleva fondo propio). Cada botón define
  el color del texto en reposo y al pasar el mouse (contraste ≥ 4,5:1). Las cifras no se cortan con
  «…»: se reducen con el ancho del recuadro (`container-type` + `cqi`) y si no caben pasan de línea. El visor muestra el marco
  oscuro y el documento como papel claro (los colores de las marcas son los del Excel).
- **Uso de la plataforma** (v6.17): `registro\logica.py` `filtrar_periodo`, `acciones_por_hora`,
  `mapa_semana_hora`, `tramos_del_dia`, `resumen_dia`, `estadisticas_periodo`; en `visual.py`
  `html_columnas`, `html_mapa_calor` y `html_linea_tiempo`.
- **Gráficos de análisis** (v6.16): `gmya\comun\estadistica.py` (porcentajes que suman 100, tramos de
  antigüedad, top N con «Otros», concentración de Pareto) y en `visual.py` `html_antiguedad`,
  `html_comparativo` (dos series por fila), `html_puente` (cascada horizontal) y `html_barras_valor`.
  Montos: `a_centavos` (mitad hacia arriba) en `comun\numeros.py`.
- **Piezas visuales** (v6.13): `gmya\ui\visual.py` (íconos SVG propios, `kpis`, `panel_resumen` con
  dona, `html_barras`, `html_area`, `grafico`). Sin dependencias nuevas ni internet. Úsalas para
  resúmenes de resultados en lugar de `st.metric` sueltos.
- **Panel de diferencias** (v6.14): vista principal de los resultados en lugar del visor.
  `gmya\ui\diferencias.py` (`mostrar_diferencias`: pestañas por concepto, resumen con dona,
  «¿Qué explica la diferencia?», buscador, filtro por causa, orden y partidas que se abren con el
  detalle A vs B; el visor de documentos queda en el interruptor «Ver los documentos originales»).
  Cada módulo arma sus datos en un adaptador sin Streamlit: `dian\diferencias.py`,
  `bancos\diferencias.py`, `pagos\diferencias.py` (modo revisión: cómo se compone el total y
  qué confirmar) y `nomina\diferencias.py` (formato del banco, conciliación de nómina y
  controles de nómina electrónica). Regla: la composición suma EXACTO total A − total B; si no,
  la pantalla muestra «Sin explicar» (nunca se esconde).
- **Regla de capas**: un archivo solo importa de capas anteriores
  (`config → comun → ui → registro/lógica de módulos → interfaces → inicio →
  app`). Así no hay importaciones circulares; la verificación lo revisa.

## 7. Reglas que se mantienen (no cambiar sin aprobación)

- La carpeta **001. EMPRESAS ACTIVAS USO DIARIO** es solo lectura.
- Las filas confidenciales que solo están en la programación anterior nunca
  se resaltan ni se marcan en lo que genera la plataforma.
- Solo un administrador puede cambiar de usuario.
- El registro de uso no guarda datos de clientes.
- Nómina: nunca se agregan ni se borran empleados del Excel; solo alertas.

## 8. Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `No se encontro run_gmyatools.py ...` | No estás en la carpeta del proyecto: `cd` a ella |
| `Las verificaciones fallaron` | Lee las líneas `ERROR` de arriba (archivo y nombre faltante) |
| `No se encontro el certificado` | Importar el .pfx en Usuario actual > Personal |
| El .exe abre y se cierra | Ejecútalo desde una consola para ver el error; la ventana espera Enter |
| `ModuleNotFoundError` al abrir el .exe | Compila de nuevo con el script (no a mano con PyInstaller) |
