"""Small deterministic foundations for the remaining engine pipelines.

These types are intentionally data first: the editor, preview and exported game
can validate the same JSON contracts before a renderer or platform backend is
selected.  The algorithms are also useful for headless gameplay tests.
"""
from collections import deque
from dataclasses import dataclass, field
import heapq
import math
import time


def _finite(value, label):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _text(value, label, limit=512):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > limit or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{label} must be nonempty text")
    return value


def _relative_path(value, label):
    value = _text(value, label, 4096)
    parts = value.replace('\\', '/').split('/')
    if value.startswith('/') or ':' in parts[0] or '..' in parts or any(not part for part in parts):
        raise ValueError(f"{label} must stay inside the project")
    return value


def _finite_vector(value, size, label, minimum=None, maximum=None):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f"{label} requires {size} numeric values")
    result = tuple(_finite(item, label) for item in value)
    if minimum is not None and any(item < minimum for item in result):
        raise ValueError(f"{label} contains a value below {minimum}")
    if maximum is not None and any(item > maximum for item in result):
        raise ValueError(f"{label} contains a value above {maximum}")
    return result


@dataclass
class TileMap:
    width: int
    height: int
    layers: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 1 <= self.width <= 4096 or not 1 <= self.height <= 4096:
            raise ValueError("Tilemap dimensions must be between 1 and 4096")
        self.layers = {str(name): list(values) for name, values in self.layers.items()}
        for values in self.layers.values():
            if len(values) != self.width * self.height:
                raise ValueError("Tilemap layer size does not match dimensions")

    def _index(self, x, y):
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise IndexError("Tilemap cell is outside the map")
        return y * self.width + x

    def get(self, layer, x, y, default=-1):
        values = self.layers.get(layer)
        return default if values is None else values[self._index(x, y)]

    def set(self, layer, x, y, tile):
        if not isinstance(tile, int) or tile < -1:
            raise ValueError("Tile index must be -1 or a nonnegative integer")
        values = self.layers.setdefault(layer, [-1] * (self.width * self.height))
        values[self._index(x, y)] = tile

    def neighbors(self, x, y):
        return [(nx, ny) for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                if 0 <= nx < self.width and 0 <= ny < self.height]


@dataclass
class SpriteStateMachine:
    states: dict
    current: str
    frame: int = 0
    elapsed: float = 0.0

    def __post_init__(self):
        if self.current not in self.states:
            raise ValueError("Sprite state does not exist")
        if not self.states or any(not isinstance(v, list) or not v for v in self.states.values()):
            raise ValueError("Sprite states require nonempty frame lists")

    def transition(self, state):
        if state not in self.states:
            raise ValueError(f"Unknown sprite state: {state}")
        if state != self.current:
            self.current, self.frame, self.elapsed = state, 0, 0.0

    def update(self, delta, fps=12.0):
        delta = _finite(delta, "Sprite delta")
        fps = _finite(fps, "Sprite fps")
        if delta < 0 or fps <= 0:
            raise ValueError("Sprite delta must be nonnegative and fps positive")
        self.elapsed += delta
        step = 1.0 / fps
        while self.elapsed >= step:
            self.elapsed -= step
            self.frame = (self.frame + 1) % len(self.states[self.current])
        return self.states[self.current][self.frame]


@dataclass(frozen=True)
class SortingLayer:
    name: str
    order: int = 0


@dataclass(frozen=True)
class RuntimeTexture:
    path: str
    width: int = 0
    height: int = 0
    filter: str = "linear"
    loaded: bool = False

    def load(self, width, height):
        if not self.path or self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("Runtime texture path must stay inside the project")
        if not 1 <= width <= 16384 or not 1 <= height <= 16384:
            raise ValueError("Runtime texture dimensions are outside the supported range")
        if self.filter not in ("nearest", "linear", "anisotropic"):
            raise ValueError("Unsupported texture filter")
        return RuntimeTexture(self.path, width, height, self.filter, True)


@dataclass
class PBRMaterial:
    base_color: tuple = (1.0, 1.0, 1.0, 1.0)
    metallic: float = 0.0
    roughness: float = 0.5
    normal_map: str = ""
    emission: tuple = (0.0, 0.0, 0.0)

    def validate(self):
        if len(self.base_color) != 4 or len(self.emission) != 3:
            raise ValueError("PBR colors require 4 and 3 channels")
        for value in (*self.base_color, *self.emission):
            _finite(value, "PBR color")
        if not 0 <= self.metallic <= 1 or not 0 <= self.roughness <= 1:
            raise ValueError("PBR metallic and roughness must be in [0, 1]")
        return self


@dataclass
class Light:
    kind: str = "point"
    color: tuple = (1.0, 1.0, 1.0)
    intensity: float = 1.0
    range: float = 10.0
    casts_shadow: bool = True

    def validate(self):
        if self.kind not in ("point", "directional", "spot") or len(self.color) != 3:
            raise ValueError("Unsupported light definition")
        if any(_finite(v, "Light color") < 0 for v in self.color) or self.intensity < 0 or self.range <= 0:
            raise ValueError("Light intensity/range must be positive")
        return self


@dataclass
class ShaderGraph:
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)

    def validate(self):
        ids = {node.get("id") for node in self.nodes}
        if None in ids or len(ids) != len(self.nodes) or len(self.nodes) > 4096:
            raise ValueError("Shader graph node IDs must be unique")
        outgoing = {node_id: [] for node_id in ids}
        for edge in self.edges:
            if not isinstance(edge, (list, tuple)) or len(edge) != 2 or edge[0] not in ids or edge[1] not in ids:
                raise ValueError("Shader graph edge references an unknown node")
            outgoing[edge[0]].append(edge[1])
        visiting, visited = set(), set()
        def visit(node_id):
            if node_id in visiting:
                raise ValueError("Shader graph contains a cycle")
            if node_id in visited:
                return
            visiting.add(node_id)
            for target in outgoing[node_id]:
                visit(target)
            visiting.remove(node_id); visited.add(node_id)
        for node_id in ids:
            visit(node_id)
        return self


@dataclass
class AnimationStateMachine:
    states: dict
    current: str
    blend: float = 0.0
    notifies: list = field(default_factory=list)

    def transition(self, state, blend=0.0):
        if state not in self.states:
            raise ValueError(f"Unknown animation state: {state}")
        if not 0 <= blend <= 1:
            raise ValueError("Animation blend must be in [0, 1]")
        self.current, self.blend = state, float(blend)

    def notify(self, time_position):
        return [event for event in self.notifies if event.get("time") == time_position and event.get("state") == self.current]


def solve_two_bone_ik(root, target, upper_length, lower_length):
    """Return a planar elbow position using a bounded two-bone IK solve."""
    root = tuple(_finite(v, "IK root") for v in root)
    target = tuple(_finite(v, "IK target") for v in target)
    if len(root) != 2 or len(target) != 2 or upper_length <= 0 or lower_length <= 0:
        raise ValueError("Two-bone IK requires positive lengths and 2D points")
    dx, dy = target[0] - root[0], target[1] - root[1]
    distance = min(max(math.hypot(dx, dy), abs(upper_length - lower_length)), upper_length + lower_length)
    angle = math.atan2(dy, dx)
    elbow_angle = math.acos(max(-1.0, min(1.0, (upper_length * upper_length + distance * distance - lower_length * lower_length) / (2 * upper_length * distance))))
    return (root[0] + upper_length * math.cos(angle + elbow_angle), root[1] + upper_length * math.sin(angle + elbow_angle))


@dataclass
class CinematicCamera:
    keyframes: list

    def evaluate(self, position):
        if not self.keyframes:
            raise ValueError("Cinematic camera requires keyframes")
        frames = sorted(self.keyframes, key=lambda item: item["time"])
        if any(not isinstance(item, dict) or "time" not in item or "value" not in item for item in frames):
            raise ValueError("Cinematic camera keyframes require time and value")
        if any(frames[index]["time"] >= frames[index + 1]["time"] for index in range(len(frames) - 1)):
            raise ValueError("Cinematic camera keyframe times must increase")
        if position <= frames[0]["time"]:
            return tuple(frames[0]["value"])
        if position >= frames[-1]["time"]:
            return tuple(frames[-1]["value"])
        for left, right in zip(frames, frames[1:]):
            if left["time"] <= position <= right["time"]:
                factor = (position - left["time"]) / (right["time"] - left["time"])
                return tuple(a + (b - a) * factor for a, b in zip(left["value"], right["value"]))
        raise AssertionError("Unreachable camera interpolation")


class NavigationGrid:
    def __init__(self, width, height, blocked=()):
        if type(width) is not int or type(height) is not int or not 1 <= width <= 4096 or not 1 <= height <= 4096:
            raise ValueError("Navigation grid dimensions must be between 1 and 4096")
        self.width, self.height = width, height
        try:
            self.blocked = {tuple(cell) for cell in blocked}
        except (TypeError, ValueError):
            raise ValueError("Navigation blocked cells must be coordinate pairs") from None
        if any(not isinstance(cell, (tuple, list)) or len(cell) != 2 or
               type(cell[0]) is not int or type(cell[1]) is not int or
               not (0 <= cell[0] < width and 0 <= cell[1] < height) for cell in self.blocked):
            raise ValueError("Navigation blocked cells must be inside the grid")

    def path(self, start, goal):
        if (not isinstance(start, (tuple, list)) or not isinstance(goal, (tuple, list)) or
                len(start) != 2 or len(goal) != 2 or
                any(type(value) is not int for value in (*start, *goal)) or
                not (0 <= start[0] < self.width and 0 <= start[1] < self.height) or
                not (0 <= goal[0] < self.width and 0 <= goal[1] < self.height)):
            raise ValueError("Navigation path endpoints must be inside the grid")
        start, goal = tuple(start), tuple(goal)
        if start in self.blocked or goal in self.blocked:
            return []
        queue, previous = deque([start]), {start: None}
        while queue:
            cell = queue.popleft()
            if cell == goal:
                result = []
                while cell is not None:
                    result.append(cell); cell = previous[cell]
                return result[::-1]
            x, y = cell
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height and neighbor not in self.blocked and neighbor not in previous:
                    previous[neighbor] = cell; queue.append(neighbor)
        return []


@dataclass
class AIController:
    state: str = "idle"
    target: str = ""
    home: tuple = (0, 0)

    def set_state(self, state):
        if state not in ("idle", "patrol", "chase", "flee", "attack"):
            raise ValueError("Unknown AI state")
        self.state = state


class WorldStreamer:
    def __init__(self, radius=1):
        if radius < 0 or radius > 64:
            raise ValueError("World streaming radius must be between 0 and 64")
        self.radius, self.loaded = radius, set()

    def update(self, center, available):
        desired = {(x, y) for x, y in available if abs(x - center[0]) <= self.radius and abs(y - center[1]) <= self.radius}
        self.loaded = desired
        return sorted(desired)


class Inventory:
    def __init__(self, capacity=32):
        if type(capacity) is not int or not 0 <= capacity <= 65536:
            raise ValueError("Inventory capacity must be between 0 and 65536")
        self.capacity, self.items = capacity, {}

    def add(self, item, count=1):
        if not isinstance(item, str) or not item or type(count) is not int or count <= 0:
            raise ValueError("Inventory item/count is invalid")
        if item not in self.items and len(self.items) >= self.capacity:
            return False
        self.items[item] = self.items.get(item, 0) + count
        return True

    def remove(self, item, count=1):
        if not isinstance(item, str) or not item or type(count) is not int or count <= 0:
            raise ValueError("Inventory item/count is invalid")
        if self.items.get(item, 0) < count:
            return False
        self.items[item] -= count
        if not self.items[item]:
            del self.items[item]
        return True


@dataclass
class Combatant:
    health: float = 100.0
    shield: float = 0.0
    alive: bool = True

    def damage(self, amount):
        amount = _finite(amount, "Damage")
        if amount < 0:
            raise ValueError("Damage cannot be negative")
        absorbed = min(self.shield, amount); self.shield -= absorbed
        self.health -= amount - absorbed
        self.alive = self.health > 0
        return absorbed


@dataclass
class Quest:
    quest_id: str
    objectives: dict
    active: bool = False
    completed: bool = False

    def start(self):
        self.active, self.completed = True, False

    def progress(self, objective, amount=1):
        if not self.active or objective not in self.objectives:
            return False
        self.objectives[objective] = max(0, self.objectives[objective] - amount)
        self.completed = all(value == 0 for value in self.objectives.values())
        return self.completed


class Autosave:
    def __init__(self, interval=30.0):
        if interval <= 0 or not math.isfinite(interval):
            raise ValueError("Autosave interval must be positive")
        self.interval, self.elapsed, self.revision = interval, 0.0, 0

    def update(self, delta):
        self.elapsed += _finite(delta, "Autosave delta")
        if self.elapsed >= self.interval:
            self.elapsed %= self.interval; self.revision += 1; return True
        return False


class Replication:
    def __init__(self, authority="server"):
        if authority not in ("server", "owner", "client"):
            raise ValueError("Replication authority must be server, owner or client")
        self.authority, self.values, self.revision = authority, {}, 0

    def set(self, key, value, authority):
        if authority != self.authority:
            return False
        self.values[key] = value
        self.revision += 1
        return True

    def snapshot(self):
        return {"authority": self.authority, "revision": self.revision, "values": dict(self.values)}


class Profiler:
    def __init__(self):
        self.samples = {}
        self._active = {}

    def begin(self, name, now=None):
        if name in self._active:
            raise ValueError("Profile scope already active")
        self._active[name] = time.perf_counter() if now is None else now

    def end(self, name, now=None):
        if name not in self._active:
            raise ValueError("Profile scope is not active")
        stop = time.perf_counter() if now is None else now
        elapsed = stop - self._active.pop(name)
        self.samples[name] = self.samples.get(name, 0.0) + elapsed
        return elapsed


class PluginRegistry:
    def __init__(self):
        self.plugins = {}

    def register(self, name, version, nodes=()):
        if not isinstance(name, str) or not name or name in self.plugins:
            raise ValueError("Plugin name must be unique")
        if not isinstance(version, str) or not version:
            raise ValueError("Plugin version is required")
        self.plugins[name] = {"version": version, "nodes": list(nodes)}


class EditorDebugState:
    def __init__(self):
        self.breakpoints, self.watches, self.accessibility = set(), {}, {}

    def watch(self, name, value):
        self.watches[name] = value

    def breakpoint(self, node_id):
        self.breakpoints.add(_text(node_id, "Breakpoint node ID", 128))

    def clear_breakpoint(self, node_id):
        self.breakpoints.discard(node_id)

    def set_accessibility_label(self, node_id, label):
        if not label:
            raise ValueError("Accessibility label cannot be empty")
        self.accessibility[node_id] = label

    def delete_nodes(self, graph, selected):
        selected = set(selected)
        result = {**graph, "nodes": [node for node in graph.get("nodes", []) if node["id"] not in selected],
                  "links": [link for link in graph.get("links", []) if link["from"][0] not in selected and link["to"][0] not in selected]}
        return result

    def rename_node(self, graph, old_id, new_id):
        """Refactor a graph node ID and all endpoint references atomically."""
        _text(old_id, "Old node ID", 128); _text(new_id, "New node ID", 128)
        if old_id == new_id or new_id in {node.get("id") for node in graph.get("nodes", [])}:
            raise ValueError("New node ID must be unique")
        result = {**graph, "nodes": [], "links": []}
        for node in graph.get("nodes", []):
            copy = dict(node)
            if copy.get("id") == old_id:
                copy["id"] = new_id
            result["nodes"].append(copy)
        for link in graph.get("links", []):
            copy = dict(link)
            for endpoint in ("from", "to"):
                value = list(copy[endpoint])
                if value[0] == old_id:
                    value[0] = new_id
                copy[endpoint] = value
            result["links"].append(copy)
        if old_id in self.breakpoints:
            self.breakpoints.remove(old_id); self.breakpoints.add(new_id)
        if old_id in self.watches:
            self.watches[new_id] = self.watches.pop(old_id)
        return result


def validate_feature_document(document):
    """Validate optional scene feature sections without changing old projects.

    These contracts deliberately remain JSON-first so the editor, headless
    runtime and exported game reject the same malformed authored metadata.
    """
    if not isinstance(document, dict):
        raise ValueError("Feature document must be an object")
    sections = document.get("features", {})
    if not isinstance(sections, dict):
        raise ValueError("features must be an object")
    allowed = {"2d", "3d", "gameplay", "editor"}
    if set(sections) - allowed:
        raise ValueError("Unknown feature section")
    for name, value in sections.items():
        if not isinstance(value, dict):
            raise ValueError(f"features.{name} must be an object")
    two_d = sections.get("2d", {})
    if "tilemap" in two_d:
        tilemap = two_d["tilemap"]
        if not isinstance(tilemap, dict):
            raise ValueError("features.2d.tilemap must be an object")
        width, height = tilemap.get("width"), tilemap.get("height")
        if type(width) is not int or type(height) is not int or not 1 <= width <= 4096 or not 1 <= height <= 4096:
            raise ValueError("features.2d.tilemap dimensions are invalid")
        layers = tilemap.get("layers", {})
        if not isinstance(layers, dict):
            raise ValueError("features.2d.tilemap.layers must be an object")
        for layer, values in layers.items():
            _text(layer, "Tilemap layer name", 128)
            if not isinstance(values, list) or len(values) != width * height or any(type(tile) is not int or tile < -1 for tile in values):
                raise ValueError(f"Tilemap layer {layer} must contain width*height tile indices")
        textures = tilemap.get("runtime_textures", [])
        if not isinstance(textures, list) or len(textures) > 1024:
            raise ValueError("features.2d.tilemap.runtime_textures must be an array")
        for path in textures:
            _relative_path(path, "Runtime texture path")
        sorting = tilemap.get("sorting_layers", [])
        if not isinstance(sorting, list) or len(sorting) > 256:
            raise ValueError("features.2d.tilemap.sorting_layers must be an array")
        names = set()
        for layer in sorting:
            if not isinstance(layer, dict) or set(layer) - {"name", "order"} or "name" not in layer or type(layer.get("order", 0)) is not int:
                raise ValueError("Invalid tilemap sorting layer")
            _text(layer["name"], "Sorting layer name", 48)
            if layer["name"] in names or not -1000000 <= layer["order"] <= 1000000:
                raise ValueError("Duplicate or out of range sorting layer")
            names.add(layer["name"])
    if "runtime_textures" in two_d:
        for path in two_d["runtime_textures"]:
            _relative_path(path, "Runtime texture path")

    three_d = sections.get("3d", {})
    pbr = three_d.get("pbr")
    if pbr is not None:
        if not isinstance(pbr, dict):
            raise ValueError("features.3d.pbr must be an object")
        _finite_vector(pbr.get("base_color", [1, 1, 1, 1]), 4, "PBR base_color", 0, 1)
        _finite_vector(pbr.get("emission", [0, 0, 0]), 3, "PBR emission", 0)
        for key in ("metallic", "roughness"):
            value = _finite(pbr.get(key, 0.0 if key == "metallic" else 0.5), f"PBR {key}")
            if not 0 <= value <= 1:
                raise ValueError(f"PBR {key} must be between 0 and 1")
        if pbr.get("normal_map"):
            _relative_path(pbr["normal_map"], "PBR normal map")
    lights = three_d.get("lights", [])
    if not isinstance(lights, list) or len(lights) > 1024:
        raise ValueError("features.3d.lights must be an array")
    for light in lights:
        if not isinstance(light, dict) or light.get("kind", "point") not in ("point", "directional", "spot"):
            raise ValueError("Unsupported light definition")
        _finite_vector(light.get("color", [1, 1, 1]), 3, "Light color", 0)
        if _finite(light.get("intensity", 1), "Light intensity") < 0 or _finite(light.get("range", 10), "Light range") <= 0:
            raise ValueError("Light intensity/range must be positive")
        for key in ("position", "direction"):
            if key in light:
                _finite_vector(light[key], 3, f"Light {key}")
        if "casts_shadow" in light and type(light["casts_shadow"]) is not bool:
            raise ValueError("Light casts_shadow must be boolean")
    shader = three_d.get("shader_graph")
    if shader is not None:
        if not isinstance(shader, dict):
            raise ValueError("features.3d.shader_graph must be an object")
        ShaderGraph(shader.get("nodes", []), shader.get("edges", [])).validate()
    animation = three_d.get("animation")
    if animation is not None:
        if not isinstance(animation, dict):
            raise ValueError("features.3d.animation must be an object")
        notifies = animation.get("notifies", [])
        if not isinstance(notifies, list) or len(notifies) > 4096:
            raise ValueError("features.3d.animation.notifies must be an array")
        for notify in notifies:
            if not isinstance(notify, dict) or set(notify) - {"clip", "name", "time"} or not all(key in notify for key in ("clip", "name", "time")):
                raise ValueError("Animation notify requires clip, name and time")
            _text(notify["clip"], "Animation notify clip")
            _text(notify["name"], "Animation notify name")
            if _finite(notify["time"], "Animation notify time") < 0:
                raise ValueError("Animation notify time must be nonnegative")
        states = animation.get("states")
        if states is not None:
            if not isinstance(states, dict) or not states:
                raise ValueError("features.3d.animation.states must be a nonempty object")
            for state, definition in states.items():
                _text(state, "Animation state", 128)
                if isinstance(definition, str):
                    _text(definition, "Animation state clip")
                elif isinstance(definition, dict):
                    if set(definition) - {"clip", "loop", "speed"} or "clip" not in definition:
                        raise ValueError("Animation state requires clip, loop and speed fields")
                    _text(definition["clip"], "Animation state clip")
                    if type(definition.get("loop", True)) is not bool:
                        raise ValueError("Animation state loop must be boolean")
                    _finite(definition.get("speed", 1.0), "Animation state speed")
                else:
                    raise ValueError("Animation state must be a clip string or object")
    if "cinematic_camera" in three_d:
        camera = three_d["cinematic_camera"]
        if not isinstance(camera, list) or any(not isinstance(key, dict) or "time" not in key or "value" not in key for key in camera):
            raise ValueError("Invalid cinematic camera keyframes")
        for key in camera:
            _finite(key["time"], "Camera keyframe time")
            _finite_vector(key["value"], 3, "Camera keyframe value")

    gameplay = sections.get("gameplay", {})
    if "navigation" in gameplay:
        nav = gameplay["navigation"]
        if not isinstance(nav, dict) or not isinstance(nav.get("grid"), list) or len(nav["grid"]) != 2:
            raise ValueError("Gameplay navigation requires a two dimensional grid")
        NavigationGrid(nav["grid"][0], nav["grid"][1], nav.get("blocked", ()))
    if "ai" in gameplay:
        ai = gameplay["ai"]
        if not isinstance(ai, dict) or ai.get("state", "idle") not in ("idle", "patrol", "chase", "flee", "attack"):
            raise ValueError("Unknown AI state")
    if "world_streaming" in gameplay:
        stream = gameplay["world_streaming"]
        if not isinstance(stream, dict):
            raise ValueError("Gameplay world_streaming must be an object")
        WorldStreamer(stream.get("radius", 1))
    if "inventory" in gameplay:
        inventory = gameplay["inventory"]
        if not isinstance(inventory, dict):
            raise ValueError("Gameplay inventory must be an object")
        Inventory(inventory.get("capacity", 32))
    if "autosave" in gameplay:
        autosave = gameplay["autosave"]
        if not isinstance(autosave, dict):
            raise ValueError("Gameplay autosave must be an object")
        Autosave(autosave.get("interval", 30.0))
    if "replication" in gameplay:
        replication = gameplay["replication"]
        if not isinstance(replication, dict):
            raise ValueError("Gameplay replication must be an object")
        Replication(replication.get("authority", "server"))
    if "profiling" in gameplay and type(gameplay["profiling"]) is not bool:
        raise ValueError("Gameplay profiling must be boolean")
    editor = sections.get("editor", {})
    for key in ("ime", "debugger", "profiler", "accessibility"):
        if key in editor and type(editor[key]) is not bool and not isinstance(editor[key], dict):
            raise ValueError(f"features.editor.{key} must be boolean or an object")
    return document
