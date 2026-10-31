# Mesh shaders

Mesh.vert.hlsl and Mesh.frag.hlsl are project shaders for the position/color/UV/
normal vertex format, combined base-color/normal samplers and per-draw material,
PBR, light and alpha uniforms. Imported factors stay separate from COLOR_0 so
entity material parameters replace them without altering shared mesh data.
The existing PositionColorTransform/SolidColor shader files remain as the original
upstream examples with their license; the renderer now uses Mesh.*.spv.

Rebuild using `tools/build_shaders.ps1`. DXC is a development tool, not a game
runtime dependency. The precompiled SPIR-V files are included for normal builds.

Compiler: Microsoft DirectXShaderCompiler v1.9.2609, dxcompiler 1.9.2609.5
(commit 01b62ad47). Installed in the shared user's Programs/dxc-1.9.2609 directory.

- Archive: https://github.com/microsoft/DirectXShaderCompiler/releases/download/v1.9.2609/dxc_2026_09_29.zip
- Verified SHA-256: ad31b1fc8443175d204f77a611fdb3ef2ec42759bdc2f1167368de24a4a7e7f1
- Flags: `-spirv -fspv-target-env=vulkan1.0 -T vs_6_0/ps_6_0 -E main`
- HLSL/SPIR-V binding rules: https://github.com/microsoft/DirectXShaderCompiler/blob/v1.9.2609/docs/SPIR-V.rst
- SDL GPU binding/color-space rules: the pinned SDL_gpu.h in deps/SDL3-3.4.18.

The active renderer now evaluates a metallic/roughness BRDF, emissive term,
up to four directional/point lights and tangent-free normal-map fallback. SDL_shadercross is
still pending for the future authored Shader Graph compiler pipeline.

UiComposite.vert/frag.hlsl and their SPIR-V are project-owned UI compositor
shaders built by the same script/compiler. They preserve RmlUi's premultiplied
sRGB layer and convert it for blending into the linear scene. See docs/ui.md.
