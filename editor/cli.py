import argparse
import json
from pathlib import Path
from .core.registry import ROOT
from .core.document import load_graph, default_scene, write_text_if_changed
from .core.compiler import compile_graph
from .core.codegen import export, generate_adapters
from .core.projects import project_snapshot,compile_project


def main():
    parser = argparse.ArgumentParser(description="Node_Engine graph compiler")
    parser.add_argument("graph", type=Path,nargs='?')
    parser.add_argument("--project",type=Path)
    parser.add_argument("--scene", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    if args.project:
        if args.graph or args.scene: parser.error('--project cannot be combined with graph or --scene')
        ir=compile_project(project_snapshot(args.project))
    else:
        if not args.graph: parser.error('Supply graph or --project')
        scene = json.loads(args.scene.read_text("utf-8")) if args.scene else default_scene()
        ir = compile_graph(load_graph(args.graph), scene)
    path = export(ir, args.output)
    write_text_if_changed(ROOT / "runtime/generated/adapters.generated.cpp", generate_adapters())
    print(path)


if __name__ == "__main__":
    main()
