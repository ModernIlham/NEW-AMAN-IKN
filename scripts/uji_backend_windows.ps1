# Menjalankan uji lokal tanpa mengubah PATH/registry pengguna atau memasang paket.
[CmdletBinding()]
param(
    [string]$PythonPath,
    [string]$DllDirectory = $env:WEASYPRINT_DLL_DIRECTORIES,
    [string]$BashPath,
    [switch]$PreflightOnly,
    [string[]]$PytestArgs = @('backend/tests/unit', '-q')
)

$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonPath) { $PythonPath = Join-Path $repoPath '.venv/Scripts/python.exe' }
$previousPath = $env:PATH
$previousDll = $env:WEASYPRINT_DLL_DIRECTORIES
$previousUtf8 = $env:PYTHONUTF8

try {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw 'Python tidak ditemukan. Buat .venv dan pasang backend/requirements.txt, atau isi -PythonPath.'
    }
    $pythonExecutable = (Resolve-Path -LiteralPath $PythonPath).Path
    if ($DllDirectory) {
        $resolvedDllDirectories = @()
        foreach ($directory in ($DllDirectory -split ';')) {
            if (-not $directory -or -not (Test-Path -LiteralPath $directory -PathType Container)) {
                throw 'Direktori DLL tidak ditemukan. Isi -DllDirectory dengan folder MSYS2 ucrt64/bin yang berisi Pango.'
            }
            $resolvedDllDirectories += (Resolve-Path -LiteralPath $directory).Path
        }
        $env:WEASYPRINT_DLL_DIRECTORIES = $resolvedDllDirectories -join ';'
    }
    if (-not $BashPath) {
        $bashCommand = Get-Command bash -CommandType Application -ErrorAction SilentlyContinue
        if ($bashCommand) { $BashPath = @($bashCommand)[0].Source }
    }
    if (-not $BashPath -or -not (Test-Path -LiteralPath $BashPath -PathType Leaf)) {
        throw 'Bash tidak ditemukan. Pasang Git for Windows atau isi -BashPath dengan bash.exe miliknya.'
    }
    $bashExecutable = (Resolve-Path -LiteralPath $BashPath).Path
    $env:PATH = (Split-Path -Parent $bashExecutable) + [IO.Path]::PathSeparator + $previousPath
    $env:PYTHONUTF8 = '1'
    Push-Location -LiteralPath $repoPath
    try {
        # Render sungguhan: import saja belum membuktikan font/DLL siap.
        $smoke = @'
import os, subprocess, sys
from weasyprint import HTML
import pypdfium2
environment = dict(os.environ)
environment.pop('BASH_ENV', None)
environment.pop('ENV', None)
result = subprocess.run([sys.argv[1], '--noprofile', '--norc', '-c', 'printf AMAN_BASH_READY'],
                        capture_output=True, text=True, timeout=15, env=environment)
assert result.returncode == 0 and result.stdout == 'AMAN_BASH_READY', 'Bash tidak siap'
data = HTML(string='<p>Uji lokal AMAN</p>').write_pdf()
assert data.startswith(b'%PDF'), 'Render tidak menghasilkan PDF'
with pypdfium2.PdfDocument(data) as document:
    assert len(document) == 1, 'Hasil render tidak satu halaman'
print('Preflight lulus: Bash, Pango, WeasyPrint, dan pembaca dokumen siap.')
'@
        $smoke | & $pythonExecutable -X utf8 - $bashExecutable
        if ($LASTEXITCODE -ne 0) {
            throw 'Preflight gagal. Periksa dependensi Python serta DLL Pango; tidak ada uji yang dilewati.'
        }
        if (-not $PreflightOnly) {
            & $pythonExecutable -X utf8 -m pytest @PytestArgs
            if ($LASTEXITCODE -ne 0) { throw "Pengujian gagal (exit code $LASTEXITCODE)." }
        }
    } finally {
        Pop-Location
    }
} finally {
    $env:PATH = $previousPath
    $env:WEASYPRINT_DLL_DIRECTORIES = $previousDll
    $env:PYTHONUTF8 = $previousUtf8
}
