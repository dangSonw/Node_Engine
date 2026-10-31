"""Capture and inspect prefab authoring assets before native/editor integration."""
import argparse
import json
from pathlib import Path

from editor.core.document import load_project, save_json
from editor.core.prefabs import capture_prefab, load_prefab_library
from editor.core.scene import asset_path


def main(argv=None):
    parser = argparse.ArgumentParser(description='Node_Engine prefab asset authoring')
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('capture', help='Save a scene subtree as a prefab asset')
    capture.add_argument('--project', type=Path, required=True)
    capture.add_argument('--root', required=True, help='Scene entity ID to capture')
    capture.add_argument('--name', required=True)
    capture.add_argument('--id', help='Stable asset ID; defaults to a UUID')
    capture.add_argument('--output', required=True, help='Project-relative .prefab.json path')
    capture.add_argument('--clear-external-references', action='store_true')
    capture.add_argument('--replace', action='store_true', help='Allow replacing an existing asset file')
    inspect = sub.add_parser('inspect', help='Validate a library and print one resolved asset')
    inspect.add_argument('--project', type=Path, required=True)
    inspect.add_argument('--prefab', required=True, help='Stable asset ID to inspect')
    inspect.add_argument('assets', nargs='+', help='Project-relative prefab files, including dependencies')
    args = parser.parse_args(argv)
    try:
        _, _, scene = load_project(args.project)
        directory = args.project.resolve().parent
        if args.command == 'capture':
            path = (directory / asset_path(args.output)).resolve()
            if not path.is_relative_to(directory):
                raise ValueError('Prefab output escapes project directory')
            if not path.name.endswith('.prefab.json'):
                raise ValueError('Prefab output must end with .prefab.json')
            if path.exists() and not args.replace:
                raise ValueError('Prefab output already exists; choose another path or use --replace')
            asset = capture_prefab(scene, args.root, args.name, asset_id=args.id,
                                   external_references='clear' if args.clear_external_references else 'reject')
            save_json(path, asset)
            # Verify the saved document with project schema compatibility as well.
            load_prefab_library(directory, [args.output], scene.get('component_definitions', []))
            print(json.dumps({'id': asset['id'], 'path': str(path), 'entities': len(asset['entities'])}, ensure_ascii=False))
        else:
            library = load_prefab_library(directory, args.assets, scene.get('component_definitions', []))
            print(json.dumps(library.resolve(args.prefab), indent=2, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
