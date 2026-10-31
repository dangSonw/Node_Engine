param([string]$Dxc = "$env:LOCALAPPDATA\Programs\dxc-1.9.2609\bin\x64\dxc.exe")
$ErrorActionPreference = 'Stop'
$shaderRoot = Join-Path (Split-Path $PSScriptRoot -Parent) 'runtime/shaders'
foreach ($shader in @('Mesh', 'UiComposite')) {
foreach ($stage in @(@('vert', 'vs_6_0'), @('frag', 'ps_6_0'))) {
    & $Dxc -spirv '-fspv-target-env=vulkan1.0' -T $stage[1] -E main `
        -Fo (Join-Path $shaderRoot "$shader.$($stage[0]).spv") (Join-Path $shaderRoot "$shader.$($stage[0]).hlsl")
    if ($LASTEXITCODE -ne 0) { throw 'Shader compilation failed' }
}
}
