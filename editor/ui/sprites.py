"""Import and edit shared sprite atlases using transactional scene commands."""
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)
from editor.core import sprites


class SpriteAssetDialog(QDialog):
    def __init__(self, asset, project_root, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Sprite Atlas'); self.asset = deepcopy(asset); self.project_root = project_root
        form = QFormLayout(self)
        self.fields = {}
        for key, label in [('name', 'Name'), ('texture', 'Image path'), ('columns', 'Columns'), ('rows', 'Rows'),
                           ('width', 'Width (world units)'), ('height', 'Height (world units)')]:
            field = QLineEdit(str(asset[key])); field.setAccessibleName('Sprite ' + key)
            form.addRow(label, field); self.fields[key] = field
        self.pivot = [QLineEdit(str(v)) for v in asset['pivot']]
        row = QHBoxLayout()
        for label, field in zip(('Pivot X', 'Pivot Y'), self.pivot):
            field.setAccessibleName('Sprite ' + label); row.addWidget(QLabel(label)); row.addWidget(field)
        form.addRow('Pivot (0–1, from bottom left)', row)
        self.filter = QComboBox(); self.filter.addItems(['nearest', 'linear']); self.filter.setCurrentText(asset['filter'])
        form.addRow('Filter', self.filter)
        note = QLabel('Frames start at 0, from left to right and top to bottom. The grid must divide the image exactly.')
        note.setWordWrap(True); form.addRow(note)
        self.error = QLabel(); self.error.setWordWrap(True); form.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def accept(self):
        try:
            value = dict(self.asset, **{k: w.text().strip() for k, w in self.fields.items()},
                         pivot=[float(w.text()) for w in self.pivot], filter=self.filter.currentText())
            for key in ('columns', 'rows'): value[key] = int(value[key])
            for key in ('width', 'height'): value[key] = float(value[key])
            sprites.validate_assets([value]); sprites.texture_file(self.project_root, value)
        except (ValueError, OSError) as error:
            self.error.setText(str(error)); return
        self.result_asset = value
        super().accept()


class SpriteLibraryDialog(QDialog):
    def __init__(self, scene, project_root, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Sprites'); self.resize(540, 420)
        self.result_scene = deepcopy(scene); self.project_root = Path(project_root)
        layout = QVBoxLayout(self)
        self.list = QListWidget(); layout.addWidget(self.list)
        row = QHBoxLayout()
        for label, callback in [('Import Image…', self.create), ('Edit…', self.edit), ('Remove', self.remove)]:
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        layout.addLayout(row)
        self.error = QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.refresh()

    def refresh(self, selected=None):
        self.list.clear()
        for asset in sprites.scene_assets(self.result_scene):
            item = QListWidgetItem(f"{asset['name']} · {asset['columns'] * asset['rows']} frames")
            item.setData(Qt.ItemDataRole.UserRole, asset['id']); item.setToolTip(asset['texture']); self.list.addItem(item)
            if asset['id'] == selected: self.list.setCurrentItem(item)
        if self.list.currentRow() < 0 and self.list.count(): self.list.setCurrentRow(0)

    def create(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import Sprite Image', str(self.project_root), 'Images (*.png *.jpg *.jpeg)')
        if path: self.import_image(path)

    def import_image(self, path):
        try:
            self.result_scene, sid = sprites.import_texture(self.result_scene, self.project_root, path)
        except (ValueError, OSError) as error:
            self.error.setText(str(error)); return
        self.error.clear(); self.refresh(sid)

    def edit(self):
        if not (item := self.list.currentItem()): return
        sid = item.data(Qt.ItemDataRole.UserRole)
        asset = next(a for a in sprites.scene_assets(self.result_scene) if a['id'] == sid)
        dialog = SpriteAssetDialog(asset, self.project_root, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        try:
            self.result_scene = sprites.put_asset(self.result_scene, dialog.result_asset)
        except ValueError as error:
            self.error.setText(str(error)); return
        self.error.clear(); self.refresh(sid)

    def remove(self):
        if not (item := self.list.currentItem()): return
        try:
            self.result_scene = sprites.remove_asset(self.result_scene, item.data(Qt.ItemDataRole.UserRole))
        except ValueError as error:
            self.error.setText(str(error)); return
        self.error.clear(); self.refresh()
