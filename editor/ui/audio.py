"""Import and name scene-owned sound assets with the shared scene undo command."""
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QFileDialog,QHBoxLayout,QInputDialog,
    QLabel,QListWidget,QListWidgetItem,QPushButton,QVBoxLayout)
from editor.core import audio


class SoundLibraryDialog(QDialog):
    def __init__(self,scene,root,parent=None):
        super().__init__(parent); self.setWindowTitle('Sounds'); self.resize(540,420)
        self.result_scene=deepcopy(scene); self.root=root
        layout=QVBoxLayout(self); self.list=QListWidget(); layout.addWidget(self.list)
        row=QHBoxLayout()
        for label,fn in [('Import Sound…',self.choose),('Rename…',self.rename),('Remove',self.remove)]:
            button=QPushButton(label); button.clicked.connect(fn); row.addWidget(button)
        layout.addLayout(row)
        note=QLabel('Select sounds in Play Sound nodes. A voice name identifies each independently controlled playback. Preview validates encoded audio. Removing an asset can leave missing graph references.')
        note.setWordWrap(True); layout.addWidget(note)
        self.error=QLabel(); self.error.setWordWrap(True); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.refresh()

    def refresh(self,selected=None):
        self.list.clear()
        for a in audio.scene_assets(self.result_scene):
            item=QListWidgetItem(a['name']); item.setData(Qt.UserRole,a['id']); item.setToolTip(a['file']); self.list.addItem(item)
            if a['id']==selected: self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and self.list.count(): self.list.setCurrentRow(0)

    def choose(self):
        path,_=QFileDialog.getOpenFileName(self,'Import Sound',str(self.root),'Sounds (*.wav *.ogg *.mp3 *.flac)')
        if path: self.import_sound(path)

    def import_sound(self,path):
        try: self.result_scene,sid=audio.import_sound(self.result_scene,self.root,path)
        except (ValueError,OSError) as error: self.error.setText(str(error)); return
        self.error.clear(); self.refresh(sid)

    def rename(self):
        if not (item:=self.list.currentItem()): return
        sid=item.data(Qt.UserRole); old=next(a for a in audio.scene_assets(self.result_scene) if a['id']==sid)
        label,ok=QInputDialog.getText(self,'Rename Sound','Name',text=old['name'])
        if not ok: return
        try: self.result_scene=audio.put_asset(self.result_scene,dict(old,name=label.strip()))
        except ValueError as error: self.error.setText(str(error)); return
        self.error.clear(); self.refresh(sid)

    def remove(self):
        if not (item:=self.list.currentItem()): return
        self.result_scene['audio_assets']=[a for a in audio.scene_assets(self.result_scene) if a['id']!=item.data(Qt.UserRole)]
        self.refresh()
