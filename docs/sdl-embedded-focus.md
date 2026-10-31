# SDL focus in the Windows editor

The editor embeds the native SDL HWND as a child of a Qt window. Upstream SDL
3.4.18 checks `GetForegroundWindow() == hwnd` in `WIN_UpdateFocus`. A child HWND
cannot satisfy that top-level check. The application could request relative mode
and receive success while SDL still had no keyboard focus, no input-focus flag
and no cursor confinement. Actual desktop checks reproduced that combination.

Windows builds now compile SDL 3.4.18 from its pinned source archive. The patch
in `cmake/PatchSdlEmbeddedFocus.cmake` retains the original top-level condition
and also accepts a child HWND when it has `GetFocus()` and its root is the
foreground window. SDL continues to own relative motion, raw input and cursor
confinement; the engine adds no separate mouse-capture implementation.

The archive is the [official SDL release](https://github.com/libsdl-org/SDL/releases/tag/release-3.4.18).
`tools/fetch_sdl.py` verifies SHA-256
`9c75cf16330322c217dedd2e0609f1124f1b54b8633e763467b4684d0f4334a3`
and refuses to overwrite existing sources. `deps/SDL3-source-3.4.18/upstream.txt`
records provenance. CMake accepts only the exact upstream or patched bytes of
`src/video/windows/SDL_windowsevents.c`:

| Source | SHA-256 |
|---|---|
| Upstream | `e18c859aec38e658f0c44a986c4ff19a5eb0ca82b6c274013ee18d5f5d602b7e` |
| Patched | `e68e1280186fe436be89ffcf69ac01b8d9cb8ca738caae48d320f9c3cfd69ae4` |

Unknown bytes fail configuration without overwriting that file. The adapter is
idempotent; upgrades require a new source review and checks. The shared library
retains the normal SDL device, audio and GPU backends. The build stages that
library and `licenses/SDL3.txt`; SDL_image and SDL_mixer remain pinned developer
libraries. Other platforms continue to use `find_package(SDL3)` and have not
been validated for embedded cursor locking.

`tests/test_sdl_dependency.py` checks exact application, repeated application
and source-drift rejection. `tools/verify_cursor_editor.py` checks both SDL focus
flags and Windows cursor confinement, unbounded relative motion through a UI
overlay, Pause/Load/Escape/focus/error/Stop/quit behavior. The standalone verifier
checks physical keys and confirms replay does not grab the user's cursor.
Existing pointer/input-event desktop checks and whole-game checkpoint checks
with dummy and WASAPI audio cover the dependency change. See the cursor milestone
in [validation-report.md](validation-report.md) for the exact verified artifacts.
