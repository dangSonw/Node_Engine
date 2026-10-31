"""Edit one complete collider atomically, using the shared scene validator."""
from PySide6.QtWidgets import (QDialog, QFormLayout, QComboBox, QLineEdit,
    QCheckBox, QLabel, QDialogButtonBox, QHBoxLayout)
from editor.core.physics import default_body, default_character, validate_body


class RigidBodyDialog(QDialog):
    def __init__(self, body=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Rigid Body and Collider')
        form = QFormLayout(self)
        value = body or default_body()
        self.choices, self.fields, self.flags = {}, {}, {}
        for key, options in [('shape', ['box', 'sphere', 'capsule']),
                             ('motion', ['static', 'kinematic', 'dynamic'])]:
            widget = QComboBox(); widget.addItems(options); widget.setCurrentText(value[key])
            widget.setAccessibleName('Rigid body ' + key)
            form.addRow(key.title(), widget); self.choices[key] = widget
        self.extents = [QLineEdit(str(v)) for v in value['half_extents']]
        row = QHBoxLayout()
        for axis, widget in zip('XYZ', self.extents):
            widget.setAccessibleName('Box half extent ' + axis)
            row.addWidget(QLabel(axis)); row.addWidget(widget)
        form.addRow('Box half extents', row)
        for key, label in [('radius','Sphere/capsule radius'), ('half_height','Capsule half cylinder height'),
                           ('mass','Mass'), ('friction','Friction'), ('restitution','Restitution'),
                           ('gravity_scale','Gravity multiplier'), ('linear_damping','Linear damping'),
                           ('angular_damping','Angular damping'), ('mask','Collision layer mask')]:
            widget = QLineEdit(str(value[key])); widget.setAccessibleName('Rigid body ' + key)
            self.fields[key] = widget; form.addRow(label, widget)
        for key, label in [('enabled','Enabled'), ('sensor','Trigger (sensor)'),
                           ('continuous','Continuous collision detection')]:
            widget = QCheckBox(label); widget.setChecked(value[key])
            widget.setAccessibleName('Rigid body ' + key); self.flags[key] = widget; form.addRow(widget)
        self.character = QCheckBox('Character controller (upright capsule)')
        self.character.setChecked('character' in value); form.addRow(self.character)
        self.character_fields = {}
        config = value.get('character', default_character())
        for key,label in [('max_slope','Walkable slope (degrees)'),('step_height','Step height (metres)'),
                          ('floor_snap','Floor snap (metres)'),('max_strength','Push strength (newtons)')]:
            widget = QLineEdit(str(config[key])); widget.setAccessibleName('Character ' + key)
            self.character_fields[key] = widget; form.addRow(label,widget)
        note = QLabel('Dimensions are local to the entity, centered on its origin. Capsules use the Y axis. '
                      'The entity Layer controls filtering. These settings apply when the scene starts.')
        note.setWordWrap(True); form.addRow(note)
        self.error = QLabel(); self.error.setWordWrap(True); form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
        self.choices['shape'].currentTextChanged.connect(self.update_shape)
        self.character.toggled.connect(self.update_character)
        self.update_character()

    def update_character(self, *_):
        enabled = self.character.isChecked()
        if enabled:
            self.choices['shape'].setCurrentText('capsule')
            self.choices['motion'].setCurrentText('kinematic')
            self.flags['sensor'].setChecked(False)
        for widget in self.choices.values(): widget.setEnabled(not enabled)
        self.flags['sensor'].setEnabled(not enabled)
        for widget in self.character_fields.values(): widget.setEnabled(enabled)
        self.update_shape()

    def update_shape(self, *_):
        shape = self.choices['shape'].currentText()
        for widget in self.extents: widget.setEnabled(shape == 'box')
        self.fields['radius'].setEnabled(shape != 'box')
        self.fields['half_height'].setEnabled(shape == 'capsule')

    def accept(self):
        try:
            body = {key: widget.currentText() for key, widget in self.choices.items()}
            body.update({key: (int(widget.text()) if key == 'mask' else float(widget.text()))
                         for key, widget in self.fields.items()})
            body.update({key: widget.isChecked() for key, widget in self.flags.items()})
            body['half_extents'] = [float(widget.text()) for widget in self.extents]
            if self.character.isChecked():
                body['character'] = {key:float(widget.text()) for key,widget in self.character_fields.items()}
            validate_body(body)
        except ValueError as error:
            self.error.setText(str(error)); return
        self.result_body = body
        super().accept()
