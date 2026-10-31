"""Material library editing and per-entity parameters with transactional validation."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)
from editor.core import materials


class MaterialParametersDialog(QDialog):
    def __init__(self, parameters, parent=None, *, name=None):
        super().__init__(parent)
        self.setWindowTitle('Material Parameters' if name is None else 'Material Asset')
        form = QFormLayout(self)
        self.name = QLineEdit(name) if name is not None else None
        if self.name:
            self.name.setAccessibleName('Material name'); form.addRow('Name', self.name)
        self.color = [QLineEdit(str(x)) for x in parameters['color']]
        row = QHBoxLayout()
        for channel, field in zip('RGB', self.color):
            field.setAccessibleName('Material ' + channel)
            row.addWidget(QLabel(channel)); row.addWidget(field)
        form.addRow('Linear color (0–1)', row)
        self.fields = {}
        for key, label in [('opacity', 'Opacity (0–1)'), ('alpha_cutoff', 'Alpha cutoff (0–1)')]:
            field = QLineEdit(str(parameters[key])); field.setAccessibleName('Material ' + key)
            self.fields[key] = field; form.addRow(label, field)
        self.mode = QComboBox(); self.mode.addItems(['opaque', 'mask', 'blend'])
        self.mode.setCurrentText(parameters['alpha_mode']); self.mode.setAccessibleName('Material alpha mode')
        form.addRow('Alpha mode', self.mode)
        self.unlit = QCheckBox('Unlit'); self.unlit.setChecked(parameters['unlit']); form.addRow(self.unlit)
        hint = QLabel('Opacity affects blend/mask modes. Imported textures and UVs stay in use.')
        hint.setWordWrap(True); form.addRow(hint)
        self.error = QLabel(); self.error.setWordWrap(True); form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def accept(self):
        try:
            value = dict(color=[float(f.text()) for f in self.color],
                **{k: float(f.text()) for k, f in self.fields.items()},
                alpha_mode=self.mode.currentText(), unlit=self.unlit.isChecked())
            materials.validate_parameters(value)
            if self.name and not materials.entity_text(self.name.text().strip(), 512):
                raise ValueError('Material name must be nonempty and at most 512 UTF-8 bytes')
        except ValueError as error:
            self.error.setText(str(error)); return
        self.result_parameters = value
        super().accept()


class MaterialLibraryDialog(QDialog):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Materials'); self.resize(540, 420)
        self.result_scene = deepcopy(scene)
        layout = QVBoxLayout(self)
        self.list = QListWidget(); layout.addWidget(self.list)
        row = QHBoxLayout()
        for label, callback in [('New…', self.create), ('Edit…', self.edit), ('Remove', self.remove)]:
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.refresh()

    def refresh(self, selected=None):
        self.list.clear()
        for asset in materials.scene_assets(self.result_scene):
            item = QListWidgetItem(asset['name']); item.setData(Qt.ItemDataRole.UserRole, asset['id'])
            item.setToolTip(asset['id']); self.list.addItem(item)
            if asset['id'] == selected: self.list.setCurrentItem(item)
        if self.list.currentRow() < 0 and self.list.count(): self.list.setCurrentRow(0)

    def create(self):
        self.edit_asset(materials.new_asset())

    def edit(self):
        if item := self.list.currentItem():
            mid = item.data(Qt.ItemDataRole.UserRole)
            self.edit_asset(next(a for a in materials.scene_assets(self.result_scene) if a['id'] == mid))

    def edit_asset(self, asset):
        dialog = MaterialParametersDialog({k: asset[k] for k in materials.default_parameters()}, self, name=asset['name'])
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        asset = dict(asset, name=dialog.name.text().strip(), **dialog.result_parameters)
        try:
            self.result_scene = materials.put_asset(self.result_scene, asset)
        except ValueError as error:
            self.error.setText(str(error)); return
        self.error.clear(); self.refresh(asset['id'])

    def remove(self):
        if not (item := self.list.currentItem()): return
        try:
            self.result_scene = materials.remove_asset(self.result_scene, item.data(Qt.ItemDataRole.UserRole))
        except ValueError as error:
            self.error.setText(str(error)); return
        self.error.clear(); self.refresh()
