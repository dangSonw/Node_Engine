# Live prefab Apply and Reset

Open `project.json` in the editor and press Play.

- Frame 20: the left robot enlarges and its Motion.Speed changes from 90 to 45.
- Frame 60: Apply updates the template. The middle follows; the right keeps its
  explicit scale and speed overrides.
- Frame 120: Reset releases the right robot's overrides and it follows the new template.

The middle robot's timer keeps counting throughout. A queued custom event is
delivered once across Apply. Stop restores the authored scene and original template.

The Blockbench mesh is shared by all three robots. `tools/create_prefab_apply_demo.py`
recreates this project; `tools/verify_prefab_apply_workflow.py` exercises the visible
editor, rejected transactions, Build Game and preview/export GPU parity.
