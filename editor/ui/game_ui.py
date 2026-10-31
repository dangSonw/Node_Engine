"""Edit reusable game UI templates using the shared scene undo transaction."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QHBoxLayout,
    QLabel,QLineEdit,QListWidget,QListWidgetItem,QPlainTextEdit,QPushButton,QVBoxLayout)
from editor.core import ui
from pathlib import Path


class TemplateDialog(QDialog):
    def __init__(self,asset,parent=None):
        super().__init__(parent); self.setWindowTitle('UI Template'); self.resize(850,680)
        self.asset=deepcopy(asset)
        layout=QVBoxLayout(self); form=QFormLayout()
        self.name=QLineEdit(asset['name']); self.name.setAccessibleName('Template name')
        form.addRow('Name',self.name); form.addRow('ID',QLabel(asset['id'])); layout.addLayout(form)
        self.markup=QPlainTextEdit(asset['rml']); self.markup.setAccessibleName('Template RML')
        layout.addWidget(self.markup)
        note=QLabel('Use element IDs in widget nodes. Font family: node-ui. Images and styles use project-relative paths under assets/. Preview checks RML and resources.')
        note.setWordWrap(True); layout.addWidget(note)
        self.error=QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def accept(self):
        value=dict(self.asset,name=self.name.text().strip(),rml=self.markup.toPlainText())
        try: ui.validate_assets([value])
        except ValueError as error: self.error.setText(str(error)); return
        self.asset=value; super().accept()


class UiLibraryDialog(QDialog):
    def __init__(self,scene,root,parent=None):
        super().__init__(parent); self.setWindowTitle('UI Templates'); self.resize(620,440)
        self.result_scene=deepcopy(scene); self.root=root
        layout=QVBoxLayout(self); self.list=QListWidget(); layout.addWidget(self.list)
        self.list.itemDoubleClicked.connect(self.edit)
        row=QHBoxLayout()
        for label,fn in [('New HUD',self.create),('Edit…',self.edit),('Import RML…',self.choose),('Remove',self.remove)]:
            button=QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        layout.addLayout(row)
        note=QLabel('Create Widget instantiates a template. Use a unique widget name, then address controls by their element ID. Removing a template can leave missing graph references.')
        note.setWordWrap(True); layout.addWidget(note)
        self.error=QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.refresh()

    def refresh(self,selected=None):
        self.list.clear()
        for a in ui.scene_assets(self.result_scene):
            item=QListWidgetItem(a['name']); item.setData(Qt.UserRole,a['id']); item.setToolTip(a['id']); self.list.addItem(item)
            if a['id']==selected: self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and self.list.count(): self.list.setCurrentRow(0)

    def put(self,asset):
        try: self.result_scene=ui.put_asset(self.result_scene,asset)
        except ValueError as error: self.error.setText(str(error)); return
        self.error.clear(); self.refresh(asset['id'])

    def create(self): self.put(ui.new_asset())

    def edit(self,*_):
        if not (item:=self.list.currentItem()): return
        asset=next(a for a in ui.scene_assets(self.result_scene) if a['id']==item.data(Qt.UserRole))
        dialog=TemplateDialog(asset,self)
        if dialog.exec()==QDialog.Accepted: self.put(dialog.asset)
        dialog.deleteLater()

    def choose(self):
        path,_=QFileDialog.getOpenFileName(self,'Import UI Template',str(self.root),'RmlUi template (*.rml)')
        if not path: return
        try:
            source=Path(path)
            if source.stat().st_size>1024*1024: raise ValueError('UI template exceeds 1 MiB')
            self.put(ui.new_asset(source.stem,source.read_text('utf-8-sig')))
        except (ValueError,OSError) as error: self.error.setText(str(error))

    def remove(self):
        if not (item:=self.list.currentItem()): return
        self.result_scene['ui_assets']=[a for a in ui.scene_assets(self.result_scene) if a['id']!=item.data(Qt.UserRole)]
        self.refresh()
