$PythonArgs = $args
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimePython = $null
if (Test-Path -LiteralPath $venvPython) {
    try { & $venvPython --version 2>$null } catch { $global:LASTEXITCODE = 1 }
    if ($LASTEXITCODE -eq 0) { $runtimePython = $venvPython }
}
if (-not $runtimePython) {
    foreach ($package in (Get-AppxPackage -Name 'OpenAI.CodexPrimaryRuntime*' -ErrorAction SilentlyContinue | Sort-Object Version -Descending)) {
        $candidate = Join-Path $package.InstallLocation 'dependencies\python\python.exe'
        if (Test-Path -LiteralPath $candidate) { $runtimePython = $candidate; break }
    }
}
if (-not $runtimePython) {
    $bundles = Get-ChildItem -LiteralPath 'C:\Program Files\WindowsApps' -Directory -Filter 'OpenAI.CodexPrimaryRuntime*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    foreach ($bundle in $bundles) {
        $candidate = Join-Path $bundle.FullName 'dependencies\python\python.exe'
        if (Test-Path -LiteralPath $candidate) { $runtimePython = $candidate; break }
    }
    if (-not $runtimePython) { throw 'Python not found. Install Python 3.12 and recreate .venv.' }
}
if ($runtimePython -ne $venvPython) {
    $packages = Join-Path $projectRoot '.venv\Lib\site-packages'
    if (Test-Path -LiteralPath $packages) { $env:PYTHONPATH = "$packages;$env:PYTHONPATH" }
}
$env:PYTHONIOENCODING = 'utf-8'
& $runtimePython @PythonArgs
exit $LASTEXITCODE
