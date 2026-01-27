$ScriptDir = $PSScriptRoot

# Check for venv
if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $PythonCmd = "$ScriptDir\.venv\Scripts\python.exe"
} elseif (Test-Path "$ScriptDir\.venv-phobos\Scripts\python.exe") {
    $PythonCmd = "$ScriptDir\.venv-phobos\Scripts\python.exe"
} else {
    $PythonCmd = "python"
}

$CliScript = "$ScriptDir\src\phobos\scripts\cli.py"

if (-not (Test-Path $CliScript)) {
    Write-Error "Error: $CliScript does not exist"
    exit 1
}

# Add src to PYTHONPATH just in case (useful for dev without install)
$env:PYTHONPATH = "$ScriptDir\src;" + $env:PYTHONPATH

# Execute
& $PythonCmd $CliScript @args
