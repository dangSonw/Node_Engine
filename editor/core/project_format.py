"""Portable .nen manifests and declared engine compatibility."""
from copy import deepcopy
import json
from pathlib import Path
import re
import uuid
from editor import __version__

FORMAT = 'NodeEngine.Project'
FORMAT_VERSION = 1
PROJECT_FILTER = 'Node_Engine projects (*.nen project.json);;Node_Engine project (*.nen);;Legacy project (project.json)'


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Engine versions must use major.minor.patch')
    return tuple(map(int, value.split('.')))


def validate_manifest(data, *, require_nen=False):
    if not isinstance(data, dict):
        raise ValueError('Project manifest must be an object')
    if 'type_definitions' in data or 'retired_type_ids' in data:
        from .project_types import project_type_library
        project_type_library(data)
    if 'editor' in data:
        editor = data['editor']
        if not isinstance(editor, dict) or editor.get('node_workflow', 'all') not in ('all', '2d', '3d'):
            raise ValueError('Project editor.node_workflow must be all, 2d or 3d')
    if require_nen or any(key in data for key in ('format', 'format_version', 'engine', 'project_id')):
        if data.get('format') != FORMAT:
            raise ValueError('This file is not a Node_Engine .nen project')
        if type(data.get('format_version')) is not int or data['format_version'] != FORMAT_VERSION:
            raise ValueError(f"Unsupported .nen format version {data.get('format_version')}; supported: {FORMAT_VERSION}")
        try:
            uuid.UUID(data['project_id'])
        except (KeyError, ValueError, TypeError, AttributeError) as error:
            raise ValueError('Project must contain a valid project_id UUID') from error
        if not isinstance(data.get('name'), str) or not data['name'].strip():
            raise ValueError('Project name cannot be empty')
        engine = data.get('engine')
        if not isinstance(engine, dict):
            raise ValueError('Project must declare its engine versions')
        for key in ('created_with', 'last_saved_with', 'minimum_version'):
            _version(engine.get(key))
        if _version(engine['minimum_version']) > _version(__version__):
            raise ValueError(f"Project requires Node_Engine {engine['minimum_version']} or newer; installed: {__version__}")
    return data


def load_manifest(path):
    path = Path(path)
    return validate_manifest(json.loads(path.read_text('utf-8-sig')), require_nen=path.suffix.lower() == '.nen')


def nen_manifest(project):
    """Retain project identity and unknown metadata across compatible engine versions."""
    validate_manifest(project)
    result = deepcopy(project)
    result.update(format=FORMAT, format_version=FORMAT_VERSION)
    result.setdefault('project_id', str(uuid.uuid4()))
    engine = result.setdefault('engine', dict(created_with=__version__, minimum_version=__version__))
    engine['last_saved_with'] = __version__
    if _version(engine['minimum_version']) < _version(__version__):
        engine['minimum_version'] = __version__
    validate_manifest(result, require_nen=True)
    return result
