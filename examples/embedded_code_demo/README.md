# Embedded C++ Robot

Open `project.json` in the editor and press Play. The project builds its C++ hooks
before starting Preview. The robot rotates at 60 degrees per game second and
moves sideways; `updates` counts executed Update callbacks.

Select **C++: rotate robot** and press **Ctrl+Alt+C** to edit the dedicated C++
Code node. Select **Hook: move after call** to inspect an ordinary action hook:
`{{call}}` runs Set Position, then authored C++ translates the robot. Its data
input `input_0` is the Entity port. The other tabs show the generated call and
the shared runtime implementation. Save code with Ctrl+S, then Play to rebuild.

The sample uses the existing Blockbench robot asset. C++ compilation and the
native runtime are required; the example has no Python gameplay interpreter.
