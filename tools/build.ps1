param(
    [string]$Project = "examples/core_demo/project.json",
    [string]$BuildDirectory = "build"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $manifestPath = [IO.Path]::GetFullPath((Join-Path $root $Project))
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $projectRoot = Split-Path $manifestPath -Parent
    $generated = Join-Path $projectRoot "generated"
    & "$root\.venv\Scripts\python.exe" -m editor.cli --project $manifestPath --output $generated
    if ($LASTEXITCODE -ne 0) { throw "Graph compilation failed" }
    $nativeFingerprint = & "$root\.venv\Scripts\python.exe" -m editor.core.runtime_build
    if ($LASTEXITCODE -ne 0) { throw "Cannot fingerprint native sources" }
    $toolchain = Get-ChildItem "$env:LOCALAPPDATA\Programs\llvm-mingw-*\bin\clang++.exe" | Sort-Object FullName | Select-Object -Last 1
    if (-not $toolchain) { throw "Install LLVM-MinGW or configure CMake manually with your compiler." }
    $cmake = Join-Path $env:USERPROFILE ".local\bin\cmake.exe"
    $ninja = Join-Path $env:USERPROFILE ".local\bin\ninja.exe"
    $env:PATH = $toolchain.DirectoryName + ";" + $env:PATH
    $cCompiler = Join-Path $toolchain.DirectoryName 'clang.exe'
    $cOptions = @()
    $cachePath = Join-Path $BuildDirectory 'CMakeCache.txt'
    if (-not (Test-Path -LiteralPath $cachePath) -or -not (Select-String -LiteralPath $cachePath -Pattern '^CMAKE_C_COMPILER:FILEPATH=' -Quiet)) {
        $cOptions = @("-DCMAKE_C_COMPILER=$cCompiler")
    }
    & $cmake -S $root -B $BuildDirectory -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" "-DCMAKE_CXX_COMPILER=$($toolchain.FullName)" @cOptions "-DNODE_ENGINE_GENERATED=$generated/game.generated.cpp" -DCMAKE_BUILD_TYPE=Release
    if ($LASTEXITCODE -ne 0) { throw "CMake configuration failed" }
    & $cmake --build $BuildDirectory --parallel 2
    if ($LASTEXITCODE -ne 0) { throw "Native compilation failed" }
    & "$root\.venv\Scripts\python.exe" -m editor.core.runtime_build --record $BuildDirectory --expected $nativeFingerprint
    if ($LASTEXITCODE -ne 0) { throw "Native build verification failed" }
} finally {
    Pop-Location
}
