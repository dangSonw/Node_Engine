"""Edit a complete lens atomically, including its dependent clipping planes."""
from PySide6.QtWidgets import QDialog, QFormLayout, QComboBox, QLineEdit, QLabel, QDialogButtonBox
from editor.core.camera import validate_camera


class CameraDialog(QDialog):
    def __init__(self, camera, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Camera Settings')
        self.form = QFormLayout(self)
        self.projection = QComboBox()
        self.projection.setAccessibleName('Camera projection')
        self.projection.addItems(['perspective', 'orthographic'])
        self.projection.setCurrentText(camera['projection'])
        self.form.addRow('Projection', self.projection)
        self.fields = {}
        for key, label in [('fov', 'Vertical FOV (degrees)'), ('size', 'Orthographic height'),
                           ('near', 'Near clip'), ('far', 'Far clip')]:
            field = QLineEdit(str(camera[key]))
            field.setAccessibleName('Camera ' + key)
            self.fields[key] = field
            self.form.addRow(label, field)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)

    def accept(self):
        try:
            camera = {'projection': self.projection.currentText(),
                      **{key: float(field.text()) for key, field in self.fields.items()}}
            validate_camera(camera)
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.result_camera = camera
        super().accept()
