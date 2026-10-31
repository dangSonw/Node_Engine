# Static textures and material import

Open `examples/texture_demo/project.json`, then Play. The board is a reproducible
reference scene for the native renderer. Drag the center splitter to widen the
viewport when the fixed orthographic camera crops the outside columns.
Import Model accepts glTF/GLB and copies external images and buffers into Assets.
Build Game stages SDL3_image.dll together with SDL3.dll, shaders and nested assets.
The resulting game requires neither Python nor the original imported files.

Recreate the demo with `.venv/Scripts/python.exe tools/create_texture_demo.py`.
The board has ten panels, left to right:

| Row | Panels |
|---|---|
| Top | External PNG/opaque, data URI/mask, bufferView/blend over white, external JPEG, linear factor × vertex color |
| Bottom | Repeat, mirrored repeat, clamp, TEXCOORD_1 plus KHR_texture_transform, mipmap minification |

## Implemented

- PNG and JPEG in external relative URIs (including percent-encoded filenames),
  data URIs and bufferViews in glTF/GLB. Image resources are reused within a mesh;
  entities sharing a mesh share its GPU allocations.
- Per-primitive baseColorFactor, baseColorTexture, COLOR_0 (VEC3/VEC4), arbitrary
  referenced TEXCOORD_n, and KHR_texture_transform scale/rotation/offset/channel.
  Missing UV channels, non-finite values and malformed textures fail explicitly.
- Nearest/linear magnification and minification, mip filter modes, repeat,
  mirrored repeat and clamp. Mipmaps are generated for materials that request them.
- OPAQUE ignores alpha; MASK discards below alphaCutoff; BLEND draws after opaque
  surfaces with depth testing, no depth writes and stable back-to-front primitive
  sorting. Alpha blends in linear space.
- Base-color images use sRGB GPU textures; vertex/factor colors are linear.
  The SDR_LINEAR swapchain encodes the final color as sRGB. For example a linear
  factor of 0.5 renders around byte 188, while a sampled byte 128 stays 128.
- KHR_materials_unlit disables the existing fixed directional face lighting.
  An absent material now uses the glTF default white instead of the old purple.
- Failed asset decode/upload preserves the previous live scene and GPU resources.
  Texture resources are released with their mesh.

The renderer limits source vertices per primitive to one million and expanded
triangle vertices per model to three million. Each image is capped at 64 MiB
encoded/decoded and 8192 per axis; PNG/JPEG dimensions are checked before decoding.
The retained decoded images per model are capped at 256 MiB. Mipmaps and temporary
upload buffers add GPU memory beyond the decoded-pixel budget.

## Validation and limits

`tests/test_textures.py` measures actual Windows/Vulkan framebuffer pixels rather
than only comparing two implementations. `tools/verify_texture_workflow.py`
exercises the real file dialog, import, Undo/Redo, native embedding, failed reload,
save/reopen, editor Build Game and a relocated runtime package. Evidence is recorded
in `artifacts/validation/texture-*`; details are in validation-report.md.

Reusable assets, instance parameter nodes and Inspector authoring now build on
this renderer; see [materials.md](materials.md). Scene-feature PBR now covers
metallic/roughness, emissive color, imported normal textures and up to four directional
or up to four directional/point lights. Runtime texture/UV replacement, Shader Graph/SDL_shadercross,
multi-light clustering, authored normal-map UV transforms, sprites and animation
remain pending. Non-PBR meshes retain fixed face lighting; all faces are rendered
without backface culling. Transparent primitives are sorted by their centers;
intersecting transparent triangles can still have ordering artifacts. These limits
apply equally to preview and export.

The color-space correction makes older flat-color models brighter. Existing
historical screenshot hashes are not expected to match the new renderer. Only
Windows/Vulkan and the SDR_LINEAR swapchain have been exercised on this host;
unsupported swapchain composition reports an SDL initialization error.
