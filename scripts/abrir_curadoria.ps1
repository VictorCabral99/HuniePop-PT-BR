# Sobe a mesa de curadoria e abre o navegador quando ela responde.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$url = "http://127.0.0.1:8765/api/health"
$python = "C:\Users\vhcab\AppData\Local\Programs\Python\Python312\python.exe"
$outLog = Join-Path $env:TEMP "huniepop-curadoria.log"
$errLog = Join-Path $env:TEMP "huniepop-curadoria.err"

function Test-Curadoria {
    try {
        $request = [System.Net.HttpWebRequest]::Create($url)
        $request.Timeout = 2000
        $request.Proxy = $null
        $response = $request.GetResponse()
        $ok = [int]$response.StatusCode -eq 200
        $response.Close()
        return $ok
    } catch {
        return $false
    }
}

function Stop-Curadoria {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -match 'curate\.py' }
    foreach ($proc in $procs) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($procs) {
        Start-Sleep -Milliseconds 400
    }
}

function Show-Failure {
    param([string]$Detail)
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        $Detail,
        "Curadoria PT-BR"
    ) | Out-Null
}

if (-not (Test-Path -LiteralPath $python)) {
    Show-Failure "Python nao encontrado em $python"
    exit 1
}

if (-not (Test-Curadoria)) {
    Stop-Curadoria
    Remove-Item -LiteralPath $outLog, $errLog -ErrorAction SilentlyContinue
    # ShellExecute, sem redirecionar daqui: se o processo herdar o console
    # deste script, ele morre quando o atalho fecha.
    $shell = New-Object -ComObject WScript.Shell
    $shell.CurrentDirectory = $root
    $launch = "cmd /c `"`"$python`" scripts\curate.py >> `"$outLog`" 2>&1`""
    $shell.Run($launch, 0, $false) | Out-Null
    $ready = $false
    for ($i = 0; $i -lt 50; $i++) {
        if (Test-Curadoria) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) {
        $tail = ""
        if (Test-Path -LiteralPath $errLog) {
            $tail = (Get-Content -LiteralPath $errLog -Tail 12 -ErrorAction SilentlyContinue) -join "`n"
        }
        if (-not $tail) {
            $tail = "O servidor nao respondeu em http://127.0.0.1:8765."
        }
        Show-Failure $tail
        exit 1
    }
}

Start-Process "http://127.0.0.1:8765"
