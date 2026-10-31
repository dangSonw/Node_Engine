from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QCheckBox, QSpinBox, QComboBox
from editor.core.document import create_project, save_json
from editor.core.scene import is_active
from editor.ui.main_window import MainWindow
from tests.test_entities import make_scene


def test_activity_and_layer_inspector_undo_save_and_parent_inheritance(app, tmp_path):
    project = create_project(tmp_path/'game','Activity')
    save_json(project.parent/'scenes/main.json',make_scene())
    window = MainWindow(project,QSettings(str(tmp_path/'layout.ini'),QSettings.IniFormat))
    window.refresh_hierarchy('player')
    def widget(kind, label):
        return next(w for w in window.inspector.findChildren(kind) if w.accessibleName()==label)
    def value(eid, prop, default):
        return next(e for e in window.scene['entities'] if e['id']==eid).get(prop,default)
    QTest.keyClick(widget(QCheckBox,'player active'),Qt.Key.Key_Space)
    assert value('player','active',True) is False and not is_active(window.scene,'grandchild')
    assert '[inactive]' in window.hierarchy.topLevelItem(0).child(0).text(0)
    window.refresh_hierarchy('child')
    assert widget(QCheckBox,'child active').isChecked()  # Local flag survives disabled ancestry.
    widget(QSpinBox,'child layer').setValue(31)
    assert value('child','layer',0)==31
    window.actions['Undo'].trigger(); assert value('child','layer',0)==0
    window.actions['Redo'].trigger(); assert value('child','layer',0)==31
    parent=widget(QComboBox,'child parent'); parent.setCurrentIndex(parent.findData(''))
    assert is_active(window.scene,'grandchild')
    window.actions['Undo'].trigger(); assert not is_active(window.scene,'grandchild')
    assert window.save_project()
    before=window.signature(); window.open_project(project)
    assert window.signature()==before and not window.dirty
    window.refresh_hierarchy('child')
    assert widget(QSpinBox,'child layer').value()==31
    assert widget(QCheckBox,'child active').isChecked() and not is_active(window.scene,'child')
    window.close()
