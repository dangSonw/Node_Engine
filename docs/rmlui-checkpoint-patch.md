# Local checkpoint adapter

`cmake/PatchRmlUiCheckpoint.cmake` applies this patch during CMake configuration.
It accepts only the SHA-256 of the pinned upstream header or the exact patched
header, skips an already applied patch without touching its timestamp, and fails
before writing if upstream bytes differ. The helper is part of the native build
fingerprint. `tests/test_runtime_build.py` exercises a clean copy, repeated
configuration, and rejection of an unknown revision. This tracked file and the
helper preserve the patch when the ignored dependency directory is reinstalled.

The pinned RmlUi 6.3 source includes two inline accessors in
`Include/RmlUi/Core/Context.h`: `GetDocumentFocusHistory` and
`SetDocumentFocusHistory`. They let Node_Engine preserve RmlUi's real document
focus history when loading a UI checkpoint. Replaying public `Focus()` calls
does not reproduce the state left by hiding the last focused document, and
loses the fallback document when several HUD windows are hidden in sequence.

`ClearCheckpointFocus` also restores a context with no focused document. The
upstream context root has no owner document, so calling its public `Focus()`
returns false. The method is declared by the pinned header patch and defined in
`runtime/src/ui_session.cpp`. It dispatches the normal blur transition through
`OnFocusChange`, clears the root focus chain, and retains each document's own
focus leaf. The patch helper upgrades the prior known adapter as well as clean
upstream bytes; unknown revisions still fail without writes.

The runtime validates the stored document names and reconstructs pointers in a
candidate context. The history always begins with that context's root and has
no duplicate documents. No serialized native pointers are accepted. The adapter
changes no default RmlUi behavior and adds no object-layout fields.

When upgrading RmlUi, review this adapter alongside `UiSession` checkpoint
restoration and run `tools/verify_ui_checkpoint.py`.
