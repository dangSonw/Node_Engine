# Dependencies and provenance

Python is the existing shared uv-managed CPython 3.13.17 installation. Project
packages go in `.venv`; the Python runtime is not copied into `.codex`.
CMake and Ninja are shared user tools installed through `uv tool install`.
The C++ compiler is the upstream LLVM-MinGW UCRT x86_64 distribution, installed
under the user's `AppData/Local/Programs` directory.

Native dependencies currently downloaded to `deps/`:

- Jolt Physics 5.6.0, pinned source archive and MIT license. Commit, archive URL
  and SHA-256 are in `deps/JoltPhysics-5.6.0/upstream.txt`; `tools/fetch_jolt.py`
  verifies downloads. `cmake/PhysicsDependencies.cmake` builds it statically with
  double precision positions, deterministic options and a single-thread job
  system. `licenses/Jolt.txt` is staged with each build. Primitive bodies and
  CharacterVirtual controllers are integrated with graph/editor/host/checkpoint
  paths. See [physics.md](physics.md) and [characters.md](characters.md) for
  verified workflows and remaining features.

- ozz-animation 0.17.0, MIT source archive pinned to
  `744eb9d99f606eda849acb0b1204f7a3dc20bca1`. `tools/fetch_ozz.py` checks SHA-256
  and preserves existing sources; provenance is in `deps/ozz-animation-0.17.0/upstream.txt`.
  `cmake/AnimationDependencies.cmake` builds the native asset/evaluation module
  with tools, FBX, samples and upstream tests disabled. The library requires
  CMake 3.30+, now the engine's declared minimum. `licenses/ozz-animation.txt`
  is staged by the build. Skeleton/pose evaluation, shared playback nodes,
  CPU skinning streamed to SDL_GPU and animation checkpoints are verified.
  See [animation.md](animation.md).

- RmlUi 6.3 and FreeType 2.15.0, pinned source archives and SHA-256 provenance
  in `deps/RmlUi-6.3/upstream.txt` and `deps/freetype-2.15.0/upstream.txt`.
  RmlUi uses MIT; FreeType uses its FreeType License option. The packaged sample
  font keeps `Samples/assets/LICENSE.txt`. All native entry points link both
  libraries statically, with Lua, samples and optional font codecs disabled.
  Shared SDL GPU/session integration lives in `cmake/UiDependencies.cmake`.
  Builds stage the font and license files, and headless UI uses SDL_image for
  the same resource preflight/layout as GPU UI. See [ui.md](ui.md).

- SDL 3.4.18, pinned source archive built as a shared library on Windows.
  `tools/fetch_sdl.py` verifies the archive hash; provenance is in
  `deps/SDL3-source-3.4.18/upstream.txt`. CMake applies a hash-checked child-window
  focus adapter for the Qt viewport and stages the zlib license. SDL_image/mixer
  keep their pinned developer libraries. See [SDL focus adapter](sdl-embedded-focus.md).
- SDL_image 3.4.8, upstream MinGW developer archive, PNG/JPEG decoding:
  https://github.com/libsdl-org/SDL_image/releases/tag/release-3.4.8
  Archive digest and license locations: `deps/SDL3_image-3.4.8/upstream.txt`.
- SDL_mixer 3.2.4, upstream MinGW developer archive:
  https://github.com/libsdl-org/SDL_mixer/releases/tag/release-3.2.4
  Archive digest and license locations: `deps/SDL3_mixer-3.2.4/upstream.txt`.
  The native runtime now links this library in headless and graphical builds.
  Both paths use its offline mixer; graphical interactive runs send PCM through
  an SDL device stream. Headless execution needs no playback device.
- GLM 1.0.1 (upstream source archive, MIT):
  https://github.com/g-truc/glm/releases/tag/1.0.1
- nlohmann/json 3.12.0 (upstream single header, MIT):
  https://github.com/nlohmann/json/releases/tag/v3.12.0
- PicoSHA2, MIT single-header SHA-256, pinned to commit
  `161cb3fc4170fa7a3eca9e582cebd27cc4d1fe29` of
  https://github.com/okdshin/PicoSHA2. The unmodified header, license and exact
  SHA-256 provenance are in `runtime/third_party/picosha2/`. It fingerprints game
  programs/assets on every native host; packages include `licenses/PicoSHA2.txt`.
- fastgltf 0.9.1 (upstream source, MIT), with simdjson 4.6.11 from its CMake setup:
  https://github.com/spnda/fastgltf/releases/tag/v0.9.1
- Flecs 4.1.6 (upstream amalgamated C source/header and MIT license):
  https://github.com/SanderMertens/flecs/releases/tag/v4.1.6
  Commit `fb55f3c25660425cfe1bc4cf5e6bff8b3f18a9b8`; exact URLs, SHA-256 hashes
  and build flags are recorded in `deps/flecs-4.1.6/upstream.txt`. Built as a
  static C99 library with core ECS and the OS API enabled, optional addons disabled.
  Windows links its system `dbghelp`/`ws2_32` libraries. The first integration uses
  entity-specific observers for timers and typed queued custom events. Scene
  storage now uses its C++ component API and ChildOf relationships in the same
  world; the C build enables FLECS_CPP support helpers. Typed user components use
  Flecs pairs. Native prefabs now use real Prefab/IsA relationships with inherited
  builtin components and default Override copies for mutable user component data.
  The pinned PrefabsManual was checked against these policies; a local copy is
  retained in `artifacts/validation/flecs-prefabs-pinned.md`. Gameplay Apply/Reset
  now reconciles live templates and instances while preserving surviving handles.
  Upstream API reference example:
  https://github.com/SanderMertens/flecs/blob/fb55f3c25660425cfe1bc4cf5e6bff8b3f18a9b8/examples/c/observers/entity_event/src/main.c

The original upstream SDL_gpu_examples PositionColorTransform/SolidColor shaders
remain with their license and commit. The renderer now uses project Mesh shaders
with position/color/UV, an MVP matrix, a combined texture sampler and alpha mode.
Their source and SPIR-V are included; `tools/build_shaders.ps1` rebuilds them with
shared-user DXC 1.9.2609. Exact provenance is in `runtime/shaders/mesh-provenance.md`.
SDL_shadercross remains pending; DXC is only a shader development tool.

No runtime game dependency on Qt, PySide6, NodeGraphQt or Python is permitted.
The CLI executables exercise graph/audio semantics without a window and require
SDL3.dll and SDL3_mixer.dll. node_view and node_game_view additionally require
SDL3_image.dll and their shaders/assets. CMake stages these DLLs once per output
directory. The exported game imports SDL libraries and Windows/UCRT libraries;
LLVM C++ standard/runtime libraries are statically linked.

Blockbench headless MCP is installed in the shared user's Programs directory,
uses existing Node.js 24.22.1 LTS and its npm Bun 1.4.4 dependency, and is pinned
to upstream commit 141ef78fa59eb697895ab73d4757d874ab8a2711 (package 1.10.1).
The official Blockbench desktop application remains installed separately.
