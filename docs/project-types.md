# Project Structs and Enums

**Scene > Structs and Enums…** now edits a project library. The dialog collects
the effective definitions from all scenes, including scenes that are not open.
New/edit/rename/delete operations stage graph, function/event signatures,
defaults, nested variable values and Make/Break wires together. Nothing is
written until the editor's Save action. Cancel discards the dialog's changes.

The `.nen` or legacy project manifest stores `type_definitions` with `structs`
and `enums` arrays. Definitions retain their `node_id` and `variable_id`.
Scene/graph copies remain readable by the existing compiler and must agree with
the project library, including stable identities; an implicit legacy ID cannot
silently retarget a node to a different project type. New scenes inherit the library. Existing projects without
the manifest field retain scene-owned schemas until their first project edit.

Compatible legacy types with the same name are unified even if their old IDs
differ. Types with different names that reused scene-owned IDs are assigned
distinct project IDs; existing nodes in gameplay and function bodies are remapped.
IDs occupied by components in any scene are reserved when adding a type.
Deleted identities are retired project-wide and inherited by new scenes.
An edit is rejected if any scene would lose a referenced type, an authored field
value or a connected field. Error messages identify the scene that prevented it.

If legacy scenes use the same name for different definitions, the editor opens
a scene-specific type dialog with the conflict displayed. Rename one of the
conflicting types there and save. Reopening the dialog then offers the unified
project library. Ambiguous definitions are never silently merged.

The whole project edit is one shared Undo step, including inactive documents
and project metadata. Undo after Save stages the original inactive documents
again, so saving the Undo writes a consistent project. Preview/export snapshots
include pending edits; unchanged inactive scenes are reread from disk. The native
scene format remains the same, with each scene receiving the synchronized schema.
Global nominal values retain their identity across scene changes and checkpoints.
Older checkpoints are still rejected after the compiled program changes.

Save prepares all changed files before replacing any file, publishes the
manifest last and rolls back ordinary write failures. It checks files against
their last observed bytes and refuses to overwrite external changes to a file
being saved. If the operating system also prevents rollback, original backup
files are retained and their paths are reported. This is exception recovery;
multi-file crash recovery after power loss is not certified.

Embedded C++ references are not automatically rewritten. The existing local
refactor guards still apply. User-defined collection element types remain open.
Broader GUI/performance and platform acceptance remain in the engine audit.

Evidence: `tests/test_project_types.py`, `tests/test_project_types_native.py`
and `tools/verify_project_types_editor.py`. Run the latter with `--output` and a
fresh folder to repeat the actual Qt authoring, Undo, Save and reopen proof.
