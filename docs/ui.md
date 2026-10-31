# Game UI templates and nodes

Basic game UI now runs through the shared RmlUi service in native Preview and
generated games, both headless and on SDL GPU. Nineteen UI definitions bring the
builtin registry to 352. This delivers a reusable HUD foundation; the remaining
category 18 features are listed below.

## Author a HUD

Open `examples/ui_demo/project.json` in the editor and press Play. **Add point**
increments the score/progress and rotates the Blockbench robot. The checkbox
enables the button, the slider updates `volume`, and Enter in the name field
updates the greeting. A/D moves the robot while gameplay has keyboard focus.

1. Use **Scene > UI Templates… > New HUD** to create a template. **Edit…** changes
   its name and RML markup; **Import RML…** reads an existing template. Templates
   are saved inside the scene and support Undo/Redo. Imported resource references
   must point to files already under the project's `assets/` directory.
2. Connect **On Game Start → Create Widget**. Select the template in the Inspector
   and give its instance a unique Widget name, such as `hud`.
3. Address controls by their RML element IDs. Connect **On Button Click**, **On UI
   Value Changed** or **On UI Text Submitted** to ordinary game actions. Optional
   Widget/Element filters are constant IDs; an empty filter matches all IDs.
   Widget, Element, Value and Checked outputs belong to their own event handler.
4. Use **Build Game** to compile and stage the same UI, fonts, shaders, SDL image
   dependency and licenses. The generated game needs no Python or Qt runtime.

| Nodes | Behavior |
|---|---|
| Create Widget, Destroy Widget, Widget Exists, Show Widget | Named document instances and visibility |
| Set/Get Widget Text | Literal text, button captions and text-entry values |
| Set/Get Widget Value | Progress and slider values |
| Set/Get Widget Checked, Set/Get Widget Enabled | Checkbox and form-control state |
| Focus Widget Element | Keyboard focus by element ID |
| Set Widget Style, Set Widget Position, Set Widget Size | RCSS property and pixel layout changes |
| On Button Click, On UI Value Changed, On UI Text Submitted | Deferred graph event entry points |

UI consumes handled mouse/keyboard input before gameplay actions, including
clearing held game controls when UI takes over. Escape releases the embedded
viewport to the editor. Keyboard chords use each SDL event's modifier state, so
Ctrl+A and clipboard input remain valid even if the whole chord has been queued.
Pause freezes game/UI state; Stop discards instances, and Play recreates defaults.
Loading a replacement scene preflights its templates/resources before replacing
the live scene. Missing images or references outside `assets/` preserve the
existing scene and runtime process.

## Native modules

- `runtime/src/ui_session.cpp` owns a RmlUi context per scene session. Concurrent
  sessions share the process-wide library/font lifetime, while document instances,
  element IDs, focus and event queues remain independent. A failed template load
  removes the candidate document and preserves existing instances.
- Templates are RML strings with a source URL for relative image/style resources.
  The host supplies its packaged font, registered as `node-ui`. SDL file I/O
  handles UTF-8 paths on Windows; the RmlUi stream drive separator is adapted
  consistently with its own file stream implementation.
- The service implements create/destroy/show/hide, literal Unicode text, progress,
  slider values, checkbox state, form-control enable/disable, CSS property changes
  and focus. Text setters escape RML and refuse to destroy child widgets.
- Button clicks, changes and text submission are copied into a bounded queue.
  Destroying or hiding an instance invalidates its pending events. Handlers are deliberately
  dispatched by the host after input processing, so game callbacks cannot destroy
  widgets inside RmlUi's event traversal. Programmatic changes follow RmlUi's
  change-event behavior. Enter and keypad Enter submit single-line text inputs.
  Dispatch shares the game instruction budget and reports the originating node.
  Recreating the same widget name cannot receive the destroyed instance's events;
  hidden or disabled controls cannot receive remaining queued callbacks.
- Both SDL input and deterministic context input are supported. The host supplies
  simulation time, pixel dimensions and density. The headless renderer decodes
  real image dimensions and uses the same FreeType layout and controls.
- Limits: 128 documents per session, 1 MiB RML and 4096 elements per document,
  64 KiB text setters/input, and 4096 queued events. Unknown names, invalid widget
  types and out-of-range progress/slider values are errors. RmlUi warnings/errors
  fail the current operation rather than producing a successful blank widget.

Use form controls (`input type="button"`), not a generic `button` tag, for disabled
button behavior. RmlUi has no browser default stylesheet: block containers need
`display:block`, and slider styling targets `slidertrack` / `sliderbar`.

## Color and GPU ownership

The stock SDL GPU backend writes sRGB CSS colors directly. On this engine's
`SDR_LINEAR` swapchain, `#4080c0` originally read back as `(137,188,225)`, instead
of `(64,128,192)`. `UiRenderer` now renders the UI into an RGBA8 UNORM layer,
preserving RmlUi's sRGB compositing. A fullscreen shader unpremultiplies the layer,
decodes sRGB, and premultiplies again before blending into the linear scene.
The SDR path keeps the original transfer function.

The backend source remains intact under `deps/`. `cmake/UiDependencies.cmake`
checks its two pinned source hashes and creates a build-directory adapter with
one optional explicit target format. Rendering commands, geometry, textures and
scissor handling otherwise use the upstream backend. Project-owned compositor
shaders are rebuilt with `tools/build_shaders.ps1`; precompiled SPIR-V is included.

Call `UiRenderer::begin`, `UiSession::render`, then `UiRenderer::end` after the 3D
render pass and before capture/presentation. Destroy sessions before their renderer,
and the renderer before its GPU device. Sessions are used on the runtime thread;
RmlUi globals are not a concurrent-thread API. Only SDR and SDR_LINEAR swapchains
are currently supported by the compositor. The renderer recreates its layer when
pixel dimensions change.

## Reproduce the evidence

```powershell
.venv/Scripts/python.exe tools/verify_ui_dependency.py
.venv/Scripts/python.exe tools/verify_ui_workflow.py --desktop
.venv/Scripts/python.exe -m pytest tests/test_ui.py tests/test_ui_runtime.py tests/test_runtime_build.py -q
```

The runner builds `tools/ui_probe`, packages its executable, SDL DLLs, shaders,
font and licenses into a fresh directory whose name contains Vietnamese characters,
then launches headless, SDR and SDR_LINEAR runs with a clean Windows-only PATH.
Each uses the actual `UiSession` implementation. SDL input is injected in GPU runs;
the test does not establish physical keyboard/IME behavior.

`artifacts/validation/ui-dependency-checks.json` records checks, source hashes,
pixel measurements and the isolated package path. Individual mode JSON/logs and
before/after/800x600 BMP captures sit alongside it; `ui-probe-linear.png` is the
inspected final screenshot. A new run clears the old success marker before build;
failure is persisted instead of leaving an earlier green report.

Dependency coverage includes controls and copied event payloads; enabled/hidden interaction;
literal text injection protection; failed-load rollback; independent concurrent
sessions; destroy/recreate and full library shutdown/reinitialization; Vietnamese
glyph coverage and Unicode resource paths. GPU pixel assertions cover CSS colors,
PNG sampling, UI/UI alpha blending, UI/scene alpha blending, preserved background,
scissor clipping, progress, visible slider geometry, text and resize anchors.

The workflow verifier opens the real editor, edits a template, checks Undo/Redo,
the template picker and save/reopen, and runs the embedded game. With `--desktop`,
click Add point and replace Player with `Đỗ Việt`, then press Enter when the ready
message appears. These are real OS input actions. Omitting the option skips only
this manual input gate. The rest checks Pause/Stop, failed-load rollback and an
asynchronous Build Game. It moves the source project away and launches all four
executables from a Vietnamese-named package with a Windows-only PATH. At four
and ten frames, states/events match exactly and Preview/export GPU BMPs are
byte-identical. See `artifacts/validation/ui-workflow-checks.json`,
`ui-desktop-state.json`, `ui-editor.png` and `ui-compiled.png`.

`--ui-replay path.json` supplies version-1 events (`move`, `button`, `text`, `key`,
`clear`) at zero-based frames. `examples/ui_demo/ui-replay.json` exercises clicks,
disabled behavior, checkbox, slider and Unicode submission on every native path.
Replay is deterministic context input; it does not prove physical devices or IME.

## Remaining work

Internal UI checkpoint groundwork is implemented and exercised across process
restart, including document/focus history, edited controls, scroll and queued
events. See [persistence.md](persistence.md#native-ui-checkpoints) for the 105-check
report, six matching GPU image pairs, rollback guarantees and limitations.
Public Save/Load Game nodes and transient caret/gesture/animation restoration
remain pending.

Templates currently use an RML text editor, with no visual layout designer.
Dedicated image/button-label, anchor/alignment/z-order nodes, property bindings,
navigation/gamepad, UI animation/drag/drop, IME composition, accessibility,
localization, HDR and other platforms remain incomplete or unverified. Desktop
Unicode entry/clipboard and Enter were exercised on Windows; this does not
establish Vietnamese IME composition support.
