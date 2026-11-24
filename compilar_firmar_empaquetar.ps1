<#
.SYNOPSIS
  Compila, firma y empaqueta GMYA Tools (GMYA_tools_v2.exe) en un .zip listo
  para actualizar los equipos (C:\GMYA_tools_v2\).

.DESCRIPTION
  Ejecutar desde PowerShell, parado en la carpeta del proyecto:
      .\compilar_firmar_empaquetar.ps1
  Pasos:
    1. Python (usa .venv\Scripts\python.exe si existe; si no, "python").
    2. Instala/actualiza dependencias (requirements.txt + PyInstaller).
    3. Verifica que las librerias importen.
    4. Valida que existan los archivos del proyecto.
    5. Corre las verificaciones (python -m pruebas.verificar). Si fallan,
       NO compila.
    6. PyInstaller --onedir --console -> .\dist_tools_v2\GMYA_tools_v2\
    7. Firma GMYA_tools_v2.exe con el certificado ($THUMB). Debe quedar Valid.
    8. Crea GMYA_tools_v2_<Version>.zip en la carpeta del proyecto.

.PARAMETER Version
  Texto para el nombre del .zip. Por defecto: VERSION de gmya\config.py +
  fecha (p. ej. v6.3_20261103).

.PARAMETER SinPruebas
  Compila aunque no se corran las verificaciones (no recomendado).
#>
param(
    [string]$Version = "",
    [switch]$SinPruebas
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --------------------------------------------------------------------
# Configuracion (mismos nombres de siempre: no cambia la instalacion)
# --------------------------------------------------------------------
$THUMB      = "<HUELLA_DEL_CERTIFICADO>"
$AppName    = "GMYA_tools_v2"
$MainScript = ".\run_gmyatools.py"
$AppScript  = ".\app.py"
$Paquete    = ".\gmya"
$Icon       = ".\gmya.ico"
$DistPath   = ".\dist_tools_v2"
$BuildPath  = Join-Path $env:TEMP "gmya_build_tools_v2"

function Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Falla($texto) { Write-Host ""; Write-Host "ERROR: $texto" -ForegroundColor Red; exit 1 }

# --------------------------------------------------------------------
# 1. Python
# --------------------------------------------------------------------
Paso "1/8 Python"
if (Test-Path ".\.venv\Scripts\python.exe") {
    $Py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
    Write-Host "Usando el entorno virtual del proyecto: $Py"
} else {
    $Py = "python"
    Write-Host "Usando el Python del sistema (no hay .venv en la carpeta)."
}
& $Py --version
if ($LASTEXITCODE -ne 0) { Falla "No se encontro Python. Instala Python 3.9+ y vuelve a intentar." }

# --------------------------------------------------------------------
# 2. Dependencias
# --------------------------------------------------------------------
Paso "2/8 Instalando dependencias (requirements.txt + PyInstaller)"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r .\requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { Falla "pip no pudo instalar las dependencias." }

# --------------------------------------------------------------------
# 3. Librerias
# --------------------------------------------------------------------
Paso "3/8 Verificando librerias"
& $Py -c "import streamlit, pdfplumber, openpyxl, pypdfium2, PIL, xlrd, pandas, PyInstaller; print('streamlit', streamlit.__version__)"
if ($LASTEXITCODE -ne 0) { Falla "Falta alguna libreria (ver el mensaje de arriba)." }

# --------------------------------------------------------------------
# 4. Archivos del proyecto
# --------------------------------------------------------------------
Paso "4/8 Validando archivos del proyecto"
foreach ($archivo in @($MainScript, $AppScript, "$Paquete\__init__.py", $Icon, ".\gmya\config.py")) {
    if (-not (Test-Path $archivo)) { Falla "No se encontro $archivo. Debes ejecutar el script dentro de la carpeta del proyecto." }
}
if (Test-Path ".\gmyatools_v2.py") {
    Write-Host "Aviso: gmyatools_v2.py (version anterior de un solo archivo) ya no se usa; puedes moverlo a otra carpeta." -ForegroundColor Yellow
}

$VersionApp = (Select-String -Path ".\gmya\config.py" -Pattern '^VERSION\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
if (-not $VersionApp) { Falla "No se pudo leer VERSION de gmya\config.py" }
if (-not $Version) { $Version = "{0}_{1}" -f $VersionApp, (Get-Date -Format "yyyyMMdd") }
Write-Host "Version de la plataforma: $VersionApp   |   Paquete: $Version"

# --------------------------------------------------------------------
# 5. Verificaciones
# --------------------------------------------------------------------
Paso "5/8 Verificaciones automaticas"
if ($SinPruebas) {
    Write-Host "Omitidas (-SinPruebas)." -ForegroundColor Yellow
} else {
    & $Py -m pruebas.verificar
    if ($LASTEXITCODE -ne 0) { Falla "Las verificaciones fallaron: no se compila. Corrige los errores de arriba." }
}

# --------------------------------------------------------------------
# 6. PyInstaller
# --------------------------------------------------------------------
Paso "6/8 Compilando con PyInstaller (tarda unos minutos)"
# Rutas absolutas: el .spec se escribe en TEMP (--specpath) para no
# ensuciar el proyecto, y PyInstaller resuelve las rutas desde alli.
$Raiz = (Get-Location).Path
$argumentos = @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onedir", "--console",
    "--name", $AppName,
    "--icon", (Join-Path $Raiz "gmya.ico"),
    "--paths", $Raiz,
    "--add-data", ((Join-Path $Raiz "app.py") + ";."),
    "--add-data", ((Join-Path $Raiz "gmya.ico") + ";."),
    "--collect-submodules", "gmya",
    "--hidden-import", "xlrd",
    "--hidden-import", "difflib",
    "--copy-metadata", "streamlit",
    "--collect-all", "streamlit",
    "--collect-all", "pdfplumber",
    "--collect-all", "openpyxl",
    "--collect-all", "pypdfium2",
    "--distpath", (Join-Path $Raiz "dist_tools_v2"),
    "--workpath", $BuildPath,
    "--specpath", $BuildPath
)
if (Test-Path ".\assets") { $argumentos += @("--add-data", ((Join-Path $Raiz "assets") + ";assets")) }
$argumentos += (Join-Path $Raiz "run_gmyatools.py")
& $Py @argumentos
if ($LASTEXITCODE -ne 0) { Falla "PyInstaller fallo (ver el mensaje de arriba)." }

$Exe = Join-Path $DistPath "$AppName\$AppName.exe"
if (-not (Test-Path $Exe)) { Falla "No se genero $Exe" }

# --------------------------------------------------------------------
# 7. Firma
# --------------------------------------------------------------------
Paso "7/8 Firmando $AppName.exe"
$cert = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Thumbprint -eq $THUMB } | Select-Object -First 1
if (-not $cert) { Falla "No se encontro el certificado $THUMB en Cert:\CurrentUser\My" }
Set-AuthenticodeSignature -FilePath $Exe -Certificate $cert -HashAlgorithm SHA256 | Out-Null
$firma = Get-AuthenticodeSignature -FilePath $Exe
Write-Host "Estado de la firma: $($firma.Status)"
if ($firma.Status -ne "Valid") { Falla "La firma no quedo valida ($($firma.Status)): $($firma.StatusMessage)" }

# --------------------------------------------------------------------
# 8. Zip
# --------------------------------------------------------------------
Paso "8/8 Empaquetando"
$Zip = ".\{0}_{1}.zip" -f $AppName, $Version
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $DistPath "$AppName\*") -DestinationPath $Zip -CompressionLevel Optimal

Write-Host ""
Write-Host "LISTO" -ForegroundColor Green
Write-Host "  Ejecutable : $((Resolve-Path $Exe).Path)"
Write-Host "  Paquete    : $((Resolve-Path $Zip).Path)"
Write-Host "  Instalar   : descomprimir el .zip encima de C:\GMYA_tools_v2\ en cada equipo"
Write-Host "               (conservar config_gmya.txt y GMYA_publico.cer)."
