# Blockbench integration - verified 2026-10-26

Blockbench Desktop 5.2.2 was already installed at
`C:\Users\son\AppData\Local\Programs\Blockbench\Blockbench.exe`.
The Windows firewall dialog was dismissed manually by the user with Cancel.
No firewall exception is needed for the chosen local stdio MCP workflow.

Installed upstream [Blockbench MCP](https://github.com/jasonjgardner/blockbench-mcp-plugin)
version 1.10.1, pinned commit `141ef78fa59eb697895ab73d4757d874ab8a2711`, under
`C:\Users\son\AppData\Local\Programs\blockbench-mcp`.
Its npm Bun dependency was installed after inspection of the launcher script.

The Codex server name is `blockbench-headless`, using existing user-wide Node.js
LTS to launch `node_modules/blockbench-mcp/bin/blockbench-mcp-headless.mjs`.
Arguments restrict file access to `D:\Node_Engine\examples\blockbench_demo\assets`
and disable web links. This is a local stdio server; no network listener is used.

Verification went beyond configuration: an MCP SDK client initialized the real
server, listed 23 tools, then successfully called bbmodel_create, bbmodel_edit
and bbmodel_validate. The nine-cube robot had zero reported errors or warnings.
The active Codex session may need reopening to discover newly registered tools;
the separate protocol test already proves the installed server works.

Files:

- `examples/blockbench_demo/assets/robot.bbmodel`: source written by MCP.
- `examples/blockbench_demo/assets/robot.gltf`: embedded glTF generated from
  those actual cube extents by `tools/export_cube_fixture.py`.
- `tools/make_blockbench_demo.py`: rebuilds the graph/scene and glTF fixture.

The fixture converter accepts static, untextured, unrotated cubes only. It assigns
simple lavender/cyan/ink materials to the robot parts and scales Blockbench units
by 1/16. Unsupported rotation, inflation, animation or meshes are rejected.
This conversion is separate from the Blockbench desktop glTF export feature.
The engine itself uses fastgltf to import the resulting standard glTF file.

The renderer loaded 324 expanded vertices / 108 triangles and produced identical
GPU captures and simulation snapshots in interpreted and compiled execution.
