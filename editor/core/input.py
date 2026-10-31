"""Versioned scene bindings and the shared keyboard/mouse/gamepad vocabulary."""
from copy import deepcopy
import math
import string

GAMEPAD_AXES = ('LeftX', 'LeftY', 'RightX', 'RightY', 'LeftTrigger', 'RightTrigger')
GAMEPAD_BUTTONS = ('South', 'East', 'West', 'North', 'Back', 'Guide', 'Start',
    'LeftStick', 'RightStick', 'LeftShoulder', 'RightShoulder', 'DpadUp', 'DpadDown',
    'DpadLeft', 'DpadRight', 'Misc1', 'RightPaddle1', 'LeftPaddle1', 'RightPaddle2',
    'LeftPaddle2', 'Touchpad', 'Misc2', 'Misc3', 'Misc4', 'Misc5', 'Misc6')
BUTTONS = tuple(string.ascii_uppercase + string.digits) + (
    'Space', 'Return', 'Escape', 'Tab', 'Backspace', 'Delete', 'Insert',
    'Home', 'End', 'PageUp', 'PageDown', 'Left', 'Right', 'Up', 'Down',
    'Left Shift', 'Right Shift', 'Left Ctrl', 'Right Ctrl', 'Left Alt', 'Right Alt',
    'CapsLock', 'Numlock', 'ScrollLock', 'PrintScreen', 'Pause',
    '-', '=', '[', ']', '\\', ';', "'", ',', '.', '/', '`',
    *(f'F{i}' for i in range(1, 25)),
    'MouseLeft', 'MouseRight', 'MouseMiddle', 'MouseX1', 'MouseX2',
)


def empty_input():
    return {'version': 1, 'actions': {}, 'axes': {}}


def validate_input(value):
    if not isinstance(value, dict) or type(value.get('version')) is not int or value['version'] not in (1, 2, 3):
        raise ValueError('Input bindings require version 1, 2 or 3')
    fields = {'version', 'actions', 'axes'} | ({'contexts'} if value['version'] == 3 else set())
    if set(value) != fields:
        raise ValueError('Input bindings require version, actions, axes and version-3 contexts')
    modern = value['version'] >= 2
    def valid_name(name):
        if (not isinstance(name, str) or not name.strip() or len(name.encode('utf-8')) > 128 or
                any(ord(c) < 32 or ord(c) == 127 for c in name)):
            raise ValueError('Input names need 1–128 UTF-8 bytes without control characters')
    def controller(v):
        if type(v) is not int or not 0 <= v <= 4294967295:
            raise ValueError('Binding controller must be 0 (any) or a positive 32-bit connection ID')
    def buttons(items, empty=False):
        if not isinstance(items, list) or not (0 if empty else 1) <= len(items) <= 16:
            raise ValueError('Each binding accepts at most 16 buttons; actions cannot be empty')
        identities = []
        for v in items:
            if isinstance(v, str) and v in BUTTONS:
                identity = (-1, v)
            elif modern and isinstance(v, dict) and set(v) == {'button', 'controller'}:
                controller(v['controller'])
                if not isinstance(v['button'], str) or v['button'] not in GAMEPAD_BUTTONS:
                    raise ValueError('Unknown gamepad button (case sensitive)')
                identity = (v['controller'], v['button'])
            else:
                raise ValueError('Unknown input button or invalid gamepad button binding')
            if identity in identities:
                raise ValueError('Duplicate input button binding')
            identities.append(identity)
        return set(identities)
    for group in ('actions', 'axes'):
        entries = value[group]
        if not isinstance(entries, dict) or len(entries) > 256:
            raise ValueError('At most 256 actions and 256 axes are allowed')
        for name, binding in entries.items():
            valid_name(name)
            if group == 'actions':
                buttons(binding)
            else:
                fields = ({'negative', 'positive'}, {'negative', 'positive', 'gamepads'}) if modern else ({'negative', 'positive'},)
                if not isinstance(binding, dict) or set(binding) not in fields:
                    raise ValueError('An axis needs negative/positive buttons and optional version-2 gamepads')
                negative = buttons(binding['negative'], modern)
                positive = buttons(binding['positive'], modern)
                if negative & positive:
                    raise ValueError('An axis cannot bind a button to both directions')
                pads = binding.get('gamepads', [])
                if 'gamepads' in binding and (not isinstance(pads, list) or not 1 <= len(pads) <= 16):
                    raise ValueError('An analog axis needs 1–16 gamepad bindings')
                seen = set()
                for pad in pads:
                    if not isinstance(pad, dict) or set(pad) != {'axis', 'controller', 'dead_zone', 'invert'}:
                        raise ValueError('Gamepad axis needs axis, controller, dead_zone and invert')
                    controller(pad['controller'])
                    if not isinstance(pad['axis'], str) or pad['axis'] not in GAMEPAD_AXES:
                        raise ValueError('Unknown gamepad axis')
                    if (type(pad['dead_zone']) not in (int, float) or not 0 <= pad['dead_zone'] < 1 or
                            not math.isfinite(pad['dead_zone']) or type(pad['invert']) is not bool):
                        raise ValueError('Gamepad axis needs finite dead zone in [0,1) and boolean invert')
                    identity = (pad['controller'], pad['axis'])
                    if identity in seen:
                        raise ValueError('Duplicate gamepad axis binding')
                    seen.add(identity)
                if not negative and not positive and not pads:
                    raise ValueError('An axis needs at least one button or analog binding')
    if value['version'] == 3:
        contexts = value['contexts']
        if not isinstance(contexts, dict) or len(contexts) > 64:
            raise ValueError('At most 64 input contexts are allowed')
        for name, context in contexts.items():
            valid_name(name)
            if (not isinstance(context, dict) or set(context) != {'actions', 'axes', 'enabled'} or
                    type(context['enabled']) is not bool):
                raise ValueError('Input context needs actions, axes and boolean enabled')
            for group in ('actions', 'axes'):
                names = context[group]
                if (not isinstance(names, list) or len(names) > 256 or
                        any(not isinstance(n, str) or n not in value[group] for n in names) or len(set(names)) != len(names)):
                    raise ValueError(f'Context {name}: select unique existing {group}')
            if not context['actions'] and not context['axes']:
                raise ValueError(f'Context {name}: select at least one action or axis')
    return deepcopy(value)
