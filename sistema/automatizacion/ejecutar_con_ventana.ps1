<#
Corre el robot en esta computadora, fuera de Docker, para que su navegador
pueda abrir una ventana real. Es lo que necesita la opcion "Local: ventana
del navegador en el equipo del robot" (Administracion > Parametros > Robot):
un contenedor no tiene pantalla, esta computadora si.

Uso, con el sistema ya encendido (docker compose up -d):

    powershell -ExecutionPolicy Bypass -File sistema\automatizacion\ejecutar_con_ventana.ps1

Puede quedar encendido todo el tiempo. Este robot trabaja solo mientras el
administrador tiene activado "Trabajo del robot visible" con "Local"; el
resto del tiempo espera y el robot del contenedor sigue con lo suyo. Al
cerrarlo (Ctrl+C o cerrando la ventana), el robot del contenedor retoma
todo a los pocos segundos.

La primera vez instala lo que el robot necesita (uv, Python 3.12, sus
dependencias y Chromium) en %LOCALAPPDATA%\gestion_cuentas_medicas, fuera de
la carpeta del proyecto. Con -SoloPreparar instala y termina.

Mientras este robot atiende, no se lee el buzon de correo de la clinica (el
simulador de correo no publica su puerto): revisa solo el portal de la IAFAS.
#>
param([switch]$SoloPreparar, [switch]$UnaVez)

$ErrorActionPreference = "Stop"
$raiz = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$datos = Join-Path $env:LOCALAPPDATA "gestion_cuentas_medicas\robot_local"
New-Item -ItemType Directory -Force (Join-Path $datos "sesiones_plataformas") | Out-Null

# Las mismas variables que recibe el robot del contenedor (.env del proyecto).
Get-Content (Join-Path $raiz ".env") | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z0-9_]+)=(.*)$') {
        Set-Item -Path ("Env:" + $Matches[1]) -Value $Matches[2]
    }
}

# Lo que cambia fuera de Docker: las direcciones (puertos publicados en esta
# computadora) y las carpetas.
function Valor($nombre, $por_defecto) {
    $valor = [Environment]::GetEnvironmentVariable($nombre)
    if ([string]::IsNullOrEmpty($valor)) { return $por_defecto }
    return $valor
}
$usuario_bd = Valor "USUARIO_APLICACION_BD" "gestion_cuentas_app"
$clave_bd = [uri]::EscapeDataString($env:CLAVE_USUARIO_APLICACION_BD)
$puerto_bd = Valor "POSTGRES_PORT" "5432"
$nombre_bd = Valor "POSTGRES_DB" "gestion_cuentas"
$env:URL_BASE_DATOS = "postgresql+asyncpg://${usuario_bd}:${clave_bd}@localhost:${puerto_bd}/${nombre_bd}?ssl=require"
$env:ACREDITA_SALUD_URL_BASE = "http://localhost:8100"
$env:RECEPTOR_IAFAS_URL_BASE = "http://localhost:8101"
$env:TEDEF_WEB_URL_BASE = "http://localhost:8102"
$env:RUTA_REPORTES = Join-Path $raiz "reportes"
$env:RUTA_ARTEFACTOS_S01 = Join-Path $raiz "artefactos_s01"
$env:RUTA_SESIONES_PLATAFORMAS = Join-Path $datos "sesiones_plataformas"
$env:CORREO_IMAP_HOST = ""
# Este robot tiene pantalla: es el que abre la ventana real del navegador.
$env:ROBOT_CON_PANTALLA = "true"
# El entorno de Python del robot va fuera del proyecto (y de OneDrive).
$env:UV_PROJECT_ENVIRONMENT = Join-Path $datos ".venv"
$env:PYTHONUTF8 = "1"

function Ejecutar([string[]]$orden) {
    & $orden[0] $orden[1..($orden.Length - 1)]
    if ($LASTEXITCODE -ne 0) { throw ("Fallo: " + ($orden -join " ")) }
}

Push-Location (Join-Path $raiz "sistema\automatizacion")
try {
    python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('uv') else 1)"
    if ($LASTEXITCODE -ne 0) { Ejecutar @("python", "-m", "pip", "install", "--user", "--quiet", "uv") }
    Ejecutar @("python", "-m", "uv", "sync", "--frozen", "--no-dev", "--python", "3.12")
    Ejecutar @("python", "-m", "uv", "run", "--no-sync", "playwright", "install", "chromium")
    if ($SoloPreparar) { return }

    $argumentos = @("-m", "uv", "run", "--no-sync", "python", "-m", "trabajador.principal")
    if ($UnaVez) { $argumentos += "--una-vez" }
    & python $argumentos
}
finally {
    Pop-Location
}
