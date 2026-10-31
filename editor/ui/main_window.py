import json
import hashlib
import os
from pathlib import Path
from copy import deepcopy
from shiboken6 import isValid
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QWindow
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QDockWidget,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QFormLayout, QLabel, QScrollArea,
    QToolBar, QTabWidget, QPlainTextEdit, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QPushButton, QDialog, QDialogButtonBox, QTabBar, QApplication, QSizePolicy,
    QInputDialog, QMenu, QComboBox, QCheckBox, QSpinBox,
)
from editor.core.registry import ROOT
from editor.core.document import load_project, save_json
from editor.core.projects import scene_entries, selected_entry, project_child, project_snapshot, compile_project, add_scene, convert_to_nen, save_project_documents
from editor.core.project_format import PROJECT_FILTER, nen_manifest
from editor.core import scene as scene_api
from editor.core.assets import import_model as copy_model
from editor.core.compiler import compile_graph, validate, literal_valid, GraphError, Problem
from editor.core.codegen import export, generate_node_code
from editor.core.node_code import generated_node_code, default_node_code
from editor.core.runtime_build import current as runtime_current, fingerprint as runtime_fingerprint
from editor.services import BuildService, RuntimeClient
from .graph import GraphAdapter
from .search import SearchDialog
from .theme import stylesheet
from .scene_commands import SceneCommand
from .variables import VariablesDialog
from .input import InputDialog
from editor.core.input import empty_input
from editor.core import camera as camera_api
from .camera import CameraDialog
from .physics import RigidBodyDialog
from editor.core import materials as material_api
from .materials import MaterialLibraryDialog, MaterialParametersDialog
from editor.core import sprites as sprite_api
from .sprites import SpriteLibraryDialog
from editor.core import audio as audio_api
from .audio import SoundLibraryDialog
from editor.core import ui as ui_api
from .game_ui import UiLibraryDialog
from .functions import FunctionSignatureDialog, FunctionEditorDialog, FunctionsCommand, apply_signature_edit, extract_selection
from .node_code import NodeCodeDialog
from .events import EventSignatureDialog, EventsCommand, apply_event_signature_edit
from .components import ComponentSignatureDialog
from .user_types import TypeLibraryDialog, apply_type_edit
from .project_launcher import ProjectLauncher, NewProjectDialog, remember_project
from editor.core.components import edit_instance
from editor.core.data_types import default_value
from editor.core.prefabs import add_scene_prefab, instantiate_scene_prefab
from editor.core.prefab_edits import apply_prefab_overrides, reset_prefab_instance
from editor.core.prefab_import import import_project_prefabs, register_prefab_files


class MainWindow(QMainWindow):
    def __init__(self, project_path=None, settings=None):
        super().__init__()
        self.setObjectName("ObsidianMainWindow")
        self.setMinimumSize(1120, 700)
        self.resize(1500, 900)
        self.setDockNestingEnabled(True)
        self.setStyleSheet(stylesheet())
        self.settings = settings or QSettings("NodeEngine", "ObsidianStudio")
        self.adapter = GraphAdapter(self)
        self.builder = BuildService(self)
        self.runtime = RuntimeClient(self)
        self.project_path = None
        self.project = {}
        self.project_documents = {}
        self.saved_project_documents = {}
        self.project_disk_bytes = {}
        self.scene = {}
        self.scene_id = 'main'
        self.runtime_scene = None
        self.pending_scene = None
        self.pending_focus = None
        self._signature_change_pending = False
        self.saved_signature = ""
        self.dirty = False
        self.pending_play = False
        self.pending_build = False
        self.pending_project = None
        self.reload_request = None
        self.inspected_node = None
        self.closing = False
        self.container = None
        self.foreign_window = None
        self.actions = {}
        self.docks = {}
        self._shell()
        self._actions()
        self.adapter.changed.connect(self.document_changed)
        self.adapter.selected.connect(self.inspect_node)
        self.adapter.graph.property_changed.connect(self.node_property_changed)
        self.adapter.graph.node_double_clicked.connect(lambda node:self.edit_function(node.get_property('type_id')))
        self.adapter.graph.undo_stack().indexChanged.connect(self.refresh_actions)
        self.adapter.graph.undo_stack().indexChanged.connect(self.finish_signature_edit)
        self.builder.output.connect(self.build_output.insertPlainText)
        self.builder.diagnostic.connect(self.build_diagnostic)
        self.builder.finished.connect(self.build_finished)
        self.builder.busy_changed.connect(self.refresh_actions)
        self.runtime.message.connect(self.runtime_message)
        self.runtime.log.connect(self.console.appendPlainText)
        self.runtime.stopped.connect(self.runtime_stopped)
        self.runtime.connected.connect(self.runtime_connected)
        self.restore_layout()
        if project_path:
            self.open_project(project_path)
        self.refresh_actions()

        QApplication.instance().focusChanged.connect(self.restore_native_editor_focus)

    def restore_native_editor_focus(self, previous, current):
        if (os.name != 'nt' or self.container is None or not self.isVisible() or current is None or
                not self.isAncestorOf(current) or current is self.container or self.container.isAncestorOf(current)):
            return
        # Qt can change its logical focus without releasing the foreign SDL HWND.
        import ctypes
        ctypes.windll.user32.SetFocus(ctypes.c_void_p(int(current.window().winId())))
        if self.runtime.ready:
            self.runtime.send('release_input')

    def _dock(self, title, name, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.docks[name] = dock
        return dock

    def _shell(self):
        self.toolbar = QToolBar("Main")
        self.toolbar.setObjectName("MainToolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.workspace = QTabBar()
        for name in ("Layout", "Gameplay", "Animation", "Materials", "AI", "Procedural", "Debug"):
            index = self.workspace.addTab(name)
            if name in ("Animation", "Materials", "AI", "Procedural"):
                self.workspace.setTabEnabled(index, False)
                self.workspace.setTabToolTip(index, f"Unavailable: {name} graph module is not implemented")
        self.workspace.currentChanged.connect(self.switch_workspace)
        self.toolbar.addWidget(self.workspace)
        self.toolbar.addSeparator()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("CentralSplitter")
        self.graph_panel = QWidget()
        graph_layout = QVBoxLayout(self.graph_panel)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_title = QLabel("  GAMEPLAY GRAPH   ·   Tab: add   ·   Home: frame all")
        graph_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        graph_layout.addWidget(graph_title)
        graph_layout.addWidget(self.adapter.graph.widget)
        self.viewport = QWidget()
        self.viewport_layout = QVBoxLayout(self.viewport)
        self.viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_title = QLabel("  SCENE   ·   Camera mode: View > Game Camera")
        viewport_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.viewport_layout.addWidget(viewport_title)
        self.viewport_hint = QLabel("Press Play to start the native SDL3 GPU viewport.\nImport a glTF/GLB model; PNG/JPEG textures are supported.")
        self.viewport_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewport_hint.setWordWrap(True)
        self.viewport_layout.addWidget(self.viewport_hint, 1)
        self.splitter.addWidget(self.graph_panel)
        self.splitter.addWidget(self.viewport)
        self.splitter.setSizes([680, 500])
        self.setCentralWidget(self.splitter)
        self.hierarchy = QTreeWidget()
        self.hierarchy.setMinimumWidth(180)
        self.hierarchy.setHeaderHidden(True)
        self.hierarchy.itemSelectionChanged.connect(self.select_entity)
        self.hierarchy.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hierarchy.customContextMenuRequested.connect(self.entity_menu)
        self._dock("Hierarchy", "HierarchyDock", self.hierarchy, Qt.DockWidgetArea.LeftDockWidgetArea)
        library = QWidget()
        library.setMinimumWidth(180)
        layout = QVBoxLayout(library)
        layout.setContentsMargins(6, 6, 6, 6)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Search nodes…")
        self.node_workflow = QComboBox()
        self.node_workflow.setAccessibleName('Node suggestions')
        for label, value in [('All compatible nodes', 'all'), ('2D + shared nodes', '2d'), ('3D + shared nodes', '3d')]:
            self.node_workflow.addItem(label, value)
        self.node_workflow.setToolTip('Filter suggestions. Choose All compatible nodes to combine sprite and skeletal animation nodes.')
        self.library_tree = QTreeWidget()
        self.library_tree.setHeaderHidden(True)
        layout.addWidget(self.library_search)
        layout.addWidget(self.node_workflow)
        layout.addWidget(self.library_tree)
        self.library_search.textChanged.connect(self.filter_library)
        self.node_workflow.currentIndexChanged.connect(self.change_node_workflow)
        self.library_tree.itemDoubleClicked.connect(self.add_library_node)
        self._dock("Node Library", "LibraryDock", library, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.refresh_library()
        self.inspector = QWidget()
        self.inspector_form = QFormLayout(self.inspector)
        self.inspector_form.setContentsMargins(12, 12, 12, 12)
        self.inspector_form.addRow(QLabel("Select a node or entity to edit its properties."))
        scroll = QScrollArea()
        scroll.setMinimumWidth(240)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.inspector)
        self._dock("Inspector", "InspectorDock", scroll, Qt.DockWidgetArea.RightDockWidgetArea)
        self.output_tabs = QTabWidget()
        self.assets = QListWidget()
        self.assets.itemDoubleClicked.connect(self.instantiate_asset)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(3000)
        self.build_output = QPlainTextEdit()
        self.build_output.setReadOnly(True)
        self.problems = QListWidget()
        self.problems.itemActivated.connect(self.activate_problem)
        for widget, title in ((self.assets, "Assets"), (self.console, "Console"),
                              (self.build_output, "Build Output"), (self.problems, "Problems")):
            self.output_tabs.addTab(widget, title)
        self._dock("Output", "OutputDock", self.output_tabs, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.statusBar().showMessage("Ready")
        self.metrics = QLabel("")
        self.statusBar().addPermanentWidget(self.metrics)
        self.resizeDocks([self.docks["HierarchyDock"], self.docks["InspectorDock"]], [230, 285], Qt.Orientation.Horizontal)
        self.resizeDocks([self.docks["OutputDock"]], [180], Qt.Orientation.Vertical)

    def action(self, label, callback, shortcut=None, toolbar=False, scope=None):
        action = QAction(label, self)
        action.triggered.connect(callback)
        if shortcut:
            if scope:
                binding = QShortcut(QKeySequence(shortcut), scope)
                binding.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
                binding.activated.connect(callback)
            else:
                action.setShortcut(QKeySequence(shortcut))
        self.actions[label] = action
        if toolbar:
            self.toolbar.addAction(action)
        return action

    def _actions(self):
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.action("New Project…", self.new_project, "Ctrl+N"))
        file_menu.addAction(self.action("Open Project…", self.choose_project, "Ctrl+O"))
        file_menu.addAction(self.action("Project Manager…", self.choose_project, "Ctrl+Shift+O"))
        file_menu.addAction(self.action("Save", self.save_project, "Ctrl+S", True))
        file_menu.addAction(self.action("Project Markdown…", self.edit_project_markdown, "Ctrl+Shift+M"))
        file_menu.addAction(self.action("Convert to .nen…", self.convert_project))
        file_menu.addAction(self.action("Import Model…", self.import_model))
        file_menu.addAction(self.action('Import Prefab Library…', self.import_prefab_library))
        file_menu.addAction(self.action('Register Prefab Files…', self.register_prefabs))
        self.actions['Import Prefab Library…'].setToolTip('Copy registered prefabs and models from another saved project.')
        self.actions['Register Prefab Files…'].setToolTip('Add project-local .prefab.json files and their selected dependencies to this scene.')
        file_menu.addSeparator()
        file_menu.addAction(self.action("Close", self.close))
        edit = self.menuBar().addMenu("Edit")
        viewer = self.adapter.graph.viewer()
        edit.addAction(self.action("Undo", self.adapter.graph.undo_stack().undo, "Ctrl+Z"))
        edit.addAction(self.action("Redo", self.adapter.graph.undo_stack().redo, "Ctrl+Shift+Z"))
        edit.addAction(self.action("Copy", self.adapter.graph.copy_nodes, "Ctrl+C", scope=viewer))
        edit.addAction(self.action("Paste", self.adapter.paste, "Ctrl+V", scope=viewer))
        edit.addAction(self.action("Duplicate", self.adapter.duplicate, "Ctrl+D", scope=viewer))
        edit.addAction(self.action("Delete", lambda: self.adapter.graph.delete_nodes(self.adapter.graph.selected_nodes()), "Delete", scope=viewer))
        graph_menu = self.menuBar().addMenu("Graph")
        graph_menu.addAction(self.action("Add Node…", self.quick_add, "Tab", scope=viewer))
        graph_menu.addAction(self.action("Validate", self.validate_graph))
        graph_menu.addAction(self.action('New Function…', self.new_function))
        graph_menu.addAction(self.action('Edit Function…', self.choose_function))
        graph_menu.addAction(self.action('Edit Function Signature…', self.choose_function_signature))
        graph_menu.addAction(self.action('Extract Function…',lambda:extract_selection(self,self.adapter.document(),self.scene)))
        graph_menu.addAction(self.action('View/Edit Node Code…', self.edit_node_code, 'Ctrl+Alt+C'))
        graph_menu.addAction(self.action('Define Event…', self.new_event))
        graph_menu.addAction(self.action('Edit Event Signature…', self.choose_event_signature))
        graph_menu.addAction(self.action("Focus Selection", self.adapter.graph.fit_to_selection, "F", scope=viewer))
        graph_menu.addAction(self.action("Frame All", self.frame_all, "Home", scope=viewer))
        scene_menu = self.menuBar().addMenu("Scene")
        scene_menu.addAction(self.action('New Scene…', self.new_scene))
        scene_menu.addAction(self.action('Choose Scene…', self.choose_scene))
        scene_menu.addAction(self.action('Use as Startup Scene', self.set_startup_scene))
        scene_menu.addSeparator()
        scene_menu.addAction(self.action("Create Entity", self.create_entity))
        scene_menu.addAction(self.action('Create Camera', self.create_camera))
        scene_menu.addAction(self.action('Choose Active Camera…', self.choose_camera))
        scene_menu.addAction(self.action("Duplicate Entity", self.duplicate_entity, "Ctrl+D", scope=self.hierarchy))
        scene_menu.addAction(self.action("Rename Entity…", self.rename_entity, "F2", scope=self.hierarchy))
        scene_menu.addAction(self.action("Delete Entity", self.delete_entity, "Delete", scope=self.hierarchy))
        scene_menu.addSeparator()
        scene_menu.addAction(self.action("Create Prefab from Entity…", self.create_prefab))
        scene_menu.addAction(self.action("Instantiate Prefab…", self.instantiate_prefab))
        scene_menu.addAction(self.action("Apply Prefab Overrides", self.apply_prefab))
        scene_menu.addAction(self.action("Reset Prefab Instance…", self.reset_prefab))
        self.actions['Apply Prefab Overrides'].setToolTip(
            'Update the prefab from this whole instance, preserving root placement and other instances\' overrides.')
        self.actions['Reset Prefab Instance…'].setToolTip(
            'Restore the whole instance from its prefab, keeping its root placement.')
        scene_menu.addSeparator()
        scene_menu.addAction(self.action('Scene Variables…', self.edit_variables))
        scene_menu.addAction(self.action('Structs and Enums…', self.edit_user_types))
        scene_menu.addAction(self.action('Input Actions and Axes…', self.edit_input))
        scene_menu.addAction(self.action('Materials…', self.edit_material_library))
        scene_menu.addAction(self.action('Sprites…', self.edit_sprite_library))
        scene_menu.addAction(self.action('Sounds…', self.edit_sound_library))
        scene_menu.addAction(self.action('UI Templates…', self.edit_ui_library))
        scene_menu.addAction(self.action('Define Component…', self.new_component))
        scene_menu.addAction(self.action('Add Component…', self.add_component))
        build_menu = self.menuBar().addMenu("Build")
        build_menu.addAction(self.action("Build Game", self.build_game, "Ctrl+B", True))
        build_menu.addAction(self.action("Cancel Build", self.builder.cancel))
        build_menu.addAction(self.action("Export C++", self.export_cpp))
        build_menu.addAction(self.action("Run Built Game", self.run_built))
        view = self.menuBar().addMenu("View")
        game_camera = self.action('Game Camera', self.view_game_camera)
        game_camera.setCheckable(True)
        game_camera.setChecked(True)
        game_camera.setToolTip('Use the scene camera in preview. Uncheck to orbit freely.')
        view.addAction(game_camera)
        for dock in self.docks.values():
            view.addAction(dock.toggleViewAction())
        view.addAction(self.action("Reset Layout", self.reset_layout))
        view.addAction(self.action("Save Workspace", self.save_layout))
        self.toolbar.addSeparator()
        self.action("Play", self.play, "F5", True)
        self.action("Pause", self.pause, "F6", True)
        self.action("Stop", self.stop, "Shift+F5", True)
        self.action("Commands…", self.commands, "Ctrl+P")
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.action("Node Help…", self.show_node_help, "F1"))
        help_menu.addAction(self.action("Game Template Guides…", lambda: self.show_node_help(guide='start')))
        help_menu.addSeparator()
        help_menu.addAction(self.action("About", lambda: QMessageBox.information(
            self, "Obsidian Studio", "Node_Engine\nPython editor · shared C++ / SDL3 GPU runtime\nSee docs/roadmap.md for supported and pending systems.")))

    def show_node_help(self, node=None, *, guide=None):
        from .node_help import open_help
        return open_help(self, self.adapter, node if node is not False else None, guide=guide)

    def edit_project_markdown(self):
        if self.project_path:
            from .project_markdown import ProjectMarkdownDialog
            dialog = ProjectMarkdownDialog(self.project_path, self)
            dialog.exec()
            dialog.deleteLater()

    def signature(self):
        inactive={key:value for key,value in self.project_documents.items() if key!=self.scene_id}
        return json.dumps([self.project, self.adapter.document(), self.scene, inactive], sort_keys=True, ensure_ascii=False)

    def document_changed(self):
        if self.inspected_node is not None and self.inspected_node not in self.adapter.graph.all_nodes():
            self.inspected_node = None
            self.clear_inspector()
        self.dirty = self.signature() != self.saved_signature
        self.setWindowTitle(f"{self.project.get('name', 'Node_Engine')} / {self.scene_id}{' *' if self.dirty else ''} — Obsidian Studio")

    def confirm_unsaved(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, "Unsaved changes", "Save the current project before continuing?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project()
        return True

    def choose_project(self):
        if not self.confirm_unsaved():
            return
        if self.builder.busy:
            return
        dialog=ProjectLauncher(self.settings,self,initial_project=self.project_path)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.switch_project(dialog.project_path)

    def new_project(self):
        if self.builder.busy or not self.confirm_unsaved():
            return
        dialog=NewProjectDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.switch_project(dialog.project_path)

    def convert_project(self):
        if not self.project_path or self.builder.busy or self.runtime.active or not self.confirm_unsaved():
            return
        try:
            path,_=convert_to_nen(self.project_path)
            if self.open_project(path,self.scene_id):
                self.statusBar().showMessage(f'Converted to {path.name}. Original manifest retained as a backup.',8000)
        except (OSError,ValueError) as error:
            self.console.appendPlainText(f'Conversion failed: {error}')

    def switch_project(self, path):
        if self.builder.busy:
            return
        if self.runtime.active:
            self.pending_project = path
            self.runtime.shutdown()
        else:
            self.open_project(path)

    def open_project(self, path, scene_id=None):
        if self.runtime.active or self.builder.busy:
            self.console.appendPlainText("Stop the runtime and finish/cancel the build before opening another project.")
            return False
        try:
            project, graph, scene = load_project(path,scene_id)
            snapshot=project_snapshot(path,project)
            documents=snapshot['scenes'] if 'scenes' in snapshot else {'main':dict(graph=graph,scene=scene)}
            self.adapter.load(graph, component_definitions=scene.get('component_definitions', []),
                              struct_definitions=scene.get('struct_definitions', []),
                              enum_definitions=scene.get('enum_definitions', []))
            self.project_path = Path(path).resolve()
            self.project, self.scene = project, scene
            self.project_documents=deepcopy(documents)
            self.saved_project_documents=deepcopy(documents)
            tracked=[Path(path).resolve()]+[project_child(Path(path).resolve().parent,entry[field])
                     for entry in scene_entries(project) for field in ('graph','scene')]
            self.project_disk_bytes={file:file.read_bytes() for file in tracked}
            workflow = project.get('editor', {}).get('node_workflow', 'all')
            self.node_workflow.blockSignals(True)
            self.node_workflow.setCurrentIndex(self.node_workflow.findData(workflow))
            self.node_workflow.blockSignals(False)
            self.adapter.node_workflow = workflow
            self.refresh_library()
            self.scene_id = selected_entry(project,scene_id)['id']
            self.inspected_node = None
            self.clear_inspector()
            self.refresh_hierarchy()
            self.refresh_assets()
            self.saved_signature = self.signature()
            self.document_changed()
            self.statusBar().showMessage(str(self.project_path))
            self.refresh_actions()
            if not remember_project(self.settings,self.project_path):
                self.console.appendPlainText('Project opened, but its recent-project history could not be saved.')
            return True
        except Exception as error:
            self.console.appendPlainText(f"Open failed: {error}")
            return False

    def save_project(self):
        if not self.project_path:
            return False
        try:
            project=nen_manifest(self.project) if self.project_path.suffix.lower()=='.nen' else self.project
            documents=deepcopy(self.project_documents)
            documents[self.scene_id]=dict(graph=self.adapter.document(),scene=deepcopy(self.scene))
            changed={key:value for key,value in documents.items()
                     if key==self.scene_id or value!=self.saved_project_documents.get(key)}
            save_project_documents(self.project_path,project,changed,expected=self.project_disk_bytes)
            self.project=project
            self.project_documents=deepcopy(documents); self.saved_project_documents=deepcopy(documents)
            self.project_disk_bytes={file:file.read_bytes() for file in self.project_disk_bytes}
            self.saved_signature = self.signature()
            self.document_changed()
            self.statusBar().showMessage("Project saved", 3000)
            return True
        except Exception as error:
            self.console.appendPlainText(f"Save failed: {error}")
            return False

    def snapshot_project(self, preview=False, scene=None):
        pending={key:value for key,value in self.project_documents.items()
                 if value!=self.saved_project_documents.get(key)}
        return project_snapshot(self.project_path,self.project,self.scene_id,self.adapter.document(),
                                self.scene if scene is None else scene,preview=preview,documents=pending)

    def switch_scene(self, scene_id):
        if self.builder.busy or not self.confirm_unsaved(): return False
        if self.runtime.active:
            self.pending_scene=scene_id
            self.runtime.shutdown()
        else: self.open_project(self.project_path,scene_id)
        return True

    def choose_scene(self):
        if not self.project_path: return
        entries=scene_entries(self.project)
        labels=[f"{entry['id']} — {entry.get('name',entry['id'])}" for entry in entries]
        selected,okay=QInputDialog.getItem(self,'Choose Scene','Edit scene',labels,
            next(i for i,e in enumerate(entries) if e['id']==self.scene_id),False)
        if okay: self.switch_scene(entries[labels.index(selected)]['id'])

    def new_scene(self):
        if not self.project_path or self.builder.busy: return
        scene_id,okay=QInputDialog.getText(self,'New Scene','Scene ID (letters, digits, underscore or hyphen)')
        if not okay or not self.confirm_unsaved(): return
        try:
            add_scene(self.project_path,scene_id.strip())
            if self.runtime.active:
                self.pending_scene=scene_id.strip(); self.runtime.shutdown()
            else: self.open_project(self.project_path,scene_id.strip())
        except (OSError,ValueError) as error:
            self.console.appendPlainText(f'New scene failed: {error}')

    def set_startup_scene(self):
        if self.project.get('version')!=2: return
        self.project['entry_scene']=self.scene_id
        self.document_changed(); self.refresh_actions()
        self.statusBar().showMessage(f'Startup scene: {self.scene_id}. Save to keep this choice.',4000)

    def refresh_library(self):
        self.library_tree.clear()
        available = list(self.adapter.suggested_specs())
        for category, label in self.adapter.registry.categories.items():
            root = QTreeWidgetItem([f'{category:02d}  {label}'])
            self.library_tree.addTopLevelItem(root)
            nodes = [n for n in available if n.category==category]
            for spec in nodes:
                item = QTreeWidgetItem([spec.name])
                item.setData(0,Qt.ItemDataRole.UserRole,spec.id)
                item.setToolTip(0,f'{spec.name}\nWorkflow: {spec.workflow.upper()}\nStable type ID: {spec.id}\n' + '\n'.join(f'{p.name}: {p.type}' for p in spec.inputs))
                root.addChild(item)
            if not nodes:
                hidden = any(n.category == category for n in self.adapter.available_specs())
                item = QTreeWidgetItem(['Hidden by suggestion filter' if hidden else 'Create a function in Graph menu' if category==6 else 'Unavailable — module pending'])
                item.setDisabled(True)
                root.addChild(item)
        self.library_tree.expandToDepth(0)
        self.filter_library(self.library_search.text())

    def change_node_workflow(self):
        workflow = self.node_workflow.currentData()
        self.adapter.node_workflow = workflow
        if self.project_path:
            self.project.setdefault('editor', {})['node_workflow'] = workflow
            self.document_changed()
        self.refresh_library()

    def new_function(self):
        signature = FunctionSignatureDialog(self.adapter.functions,self)
        accepted = signature.exec() == QDialog.DialogCode.Accepted
        signature.deleteLater()
        if accepted:
            definitions = self.adapter.functions + [signature.definition]
            self.edit_function(signature.definition['id'], definitions=definitions)

    def new_event(self):
        dialog=EventSignatureDialog(self.adapter.event_definitions,self)
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            self.adapter.graph.undo_stack().push(EventsCommand(self,[*self.adapter.event_definitions,dialog.definition]))
            self.library_search.setText(dialog.definition['name'])

    def choose_function(self):
        dialog = SearchDialog([(f['name'],f['id']) for f in self.adapter.functions], 'Edit Function',self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.edit_function(dialog.result_value)

    def choose_event_signature(self):
        selected=self.adapter.graph.selected_nodes()
        eid=self.adapter.registry[selected[0].get_property('type_id')].event_id if len(selected)==1 else None
        if eid not in {e['id'] for e in self.adapter.event_definitions}:
            chooser=SearchDialog([(e['name'],e['id']) for e in self.adapter.event_definitions],'Edit Event Signature',self)
            accepted=chooser.exec()==QDialog.DialogCode.Accepted; eid=chooser.result_value; chooser.deleteLater()
            if not accepted: return
        self.edit_event_signature(eid)

    def edit_event_signature(self,event_id):
        from editor.core.event_edits import migrate_event_signature
        before=self.adapter.document()
        if event_id not in {e['id'] for e in self.adapter.event_definitions}: return
        dialog=EventSignatureDialog(self.adapter.event_definitions,self,event_id=event_id,
            validator=lambda definition,origins:migrate_event_signature(before,event_id,definition,origins['inputs'],self.scene))
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        if accepted and dialog.result_document!=before:
            try: apply_event_signature_edit(self,dialog.result_document,event_id)
            except ValueError as error: self.console.appendPlainText(str(error))
        dialog.deleteLater()

    def choose_function_signature(self):
        selected=self.adapter.graph.selected_nodes()
        fid=selected[0].get_property('type_id') if len(selected)==1 else None
        if fid not in {f['id'] for f in self.adapter.functions}:
            chooser=SearchDialog([(f['name'],f['id']) for f in self.adapter.functions],'Edit Function Signature',self)
            accepted=chooser.exec()==QDialog.DialogCode.Accepted; fid=chooser.result_value; chooser.deleteLater()
            if not accepted: return
        self.edit_function_signature(fid)

    def edit_function_signature(self,function_id):
        from editor.core.function_edits import migrate_signature
        before=self.adapter.document()
        if function_id not in {f['id'] for f in self.adapter.functions}: return
        dialog=FunctionSignatureDialog(self.adapter.functions,self,function_id=function_id,
            validator=lambda definition,origins:migrate_signature(before,function_id,definition,origins,self.scene))
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        if accepted and dialog.result_document!=before:
            try: apply_signature_edit(self,dialog.result_document,function_id)
            except ValueError as error: self.console.appendPlainText(str(error))
        dialog.deleteLater()

    def finish_signature_edit(self,*_):
        if self._signature_change_pending and not self.adapter.loading:
            self._signature_change_pending=False
            if getattr(self,'_type_change_pending',False):
                self._type_change_pending=False
                self.refresh_hierarchy()
            self.inspected_node=None; self.clear_inspector()
            self.definitions_changed()

    def new_component(self):
        retired=self.scene.get('retired_type_ids',{})
        reserved={nid for nid,spec in self.adapter.registry.nodes.items() if spec.user_type}
        reserved.update(retired.get('nodes',[]))
        reserved.update(nid+role for nid in retired.get('variables',[]) for role in range(8))
        dialog = ComponentSignatureDialog(self.scene.get('component_definitions', []), self, reserved_nodes=reserved)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted:
            after = deepcopy(self.scene)
            after.setdefault('component_definitions', []).append(dialog.definition)
            self.push_scene('Define component', scene_api.validate_scene(after), self.selected_entity_id())
            self.library_search.setText(dialog.definition['name'])

    def edit_user_types(self):
        before=self.adapter.document()
        try:
            dialog=TypeLibraryDialog(before,self.scene,self,snapshot=self.snapshot_project(),scene_id=self.scene_id)
        except ValueError as error:
            if 'conflicting project type' not in str(error):
                self.console.appendPlainText('Project types: '+str(error)); return
            dialog=TypeLibraryDialog(before,self.scene,self)
            dialog.setWindowTitle('Scene Structs and Enums — resolve project conflict')
            dialog.error.setText(f'{error}\nRename the conflicting type in this scene, then save and reopen this dialog to synchronize the project.')
        accepted=dialog.exec()==QDialog.DialogCode.Accepted
        if accepted:
            if dialog.result_snapshot is None:
                try: apply_type_edit(self,dialog.result_graph,dialog.result_scene)
                except ValueError as error: self.console.appendPlainText(str(error))
                dialog.deleteLater(); return
            project=deepcopy(self.project); project['type_definitions']=deepcopy(dialog.result_snapshot['type_definitions'])
            if 'retired_type_ids' in dialog.result_snapshot:
                project['retired_type_ids']=deepcopy(dialog.result_snapshot['retired_type_ids'])
            documents=dialog.result_snapshot['scenes'] if 'scenes' in dialog.result_snapshot else {'main':dict(graph=dialog.result_graph,scene=dialog.result_scene)}
            try: apply_type_edit(self,dialog.result_graph,dialog.result_scene,project=project,documents=documents)
            except ValueError as error: self.console.appendPlainText(str(error))
        dialog.deleteLater()

    def add_component(self):
        eid = self.selected_entity_id()
        if not eid:
            return
        instances = scene_api.entity(self.scene, eid).get('components', {})
        options = [(d['name'], d['id']) for d in self.scene.get('component_definitions', [])
                   if str(d['id']) not in instances]
        dialog = SearchDialog(options, 'Add Component', self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Add component', edit_instance(self.scene, eid, dialog.result_value, 'add'), eid)
        dialog.deleteLater()

    def commit_component(self, eid, cid, operation, value=None, field=None):
        after = edit_instance(self.scene, eid, cid, operation, value, field)
        previous = getattr(self, '_preserve_entity_fields', False)
        self._preserve_entity_fields = operation in ('set', 'enable')
        try:
            self.push_scene('Edit component', after, eid)
        finally:
            self._preserve_entity_fields = previous

    def edit_function(self, function_id, *, definitions=None, focus=None, diagnostic=None):
        definitions = self.adapter.functions if definitions is None else definitions
        if function_id not in {f['id'] for f in definitions}:
            return
        scene = deepcopy(self.scene) if self.scene else None
        schema = getattr(self.adapter.registry, 'type_schema', None)
        if schema and scene is not None:
            scene['struct_definitions'] = list(schema.structs.values())
            scene['enum_definitions'] = list(schema.enums.values())
        dialog = FunctionEditorDialog(definitions,function_id,scene,self,event_definitions=self.adapter.event_definitions)
        if focus:
            dialog.adapter.focus(focus)
        if diagnostic:
            QTimer.singleShot(0, lambda: dialog.edit_node_code(diagnostic=diagnostic))
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        dialog.deleteLater()
        if accepted and dialog.result_definitions != self.adapter.functions:
            self.adapter.graph.undo_stack().push(FunctionsCommand(self,dialog.result_definitions))

    def apply_functions(self, definitions):
        self.adapter.configure_functions(definitions)
        self.definitions_changed()

    def apply_events(self, definitions):
        self.adapter.configure_functions(self.adapter.functions, definitions)
        self.definitions_changed()

    def definitions_changed(self):
        self.refresh_library()
        self.document_changed()
        self.refresh_actions()
        if self.runtime.ready:
            try:
                self.reload_preview(compile_project(self.snapshot_project(preview=True)),self.runtime.state=='running')
            except ValueError as e:
                self.console.appendPlainText(str(e))

    def activate_problem(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, dict):
            self.focus_problem(data['node'], diagnostic=data)
        else:
            self.focus_problem(data)

    def focus_problem(self, node_id, *, diagnostic=None):
        if not node_id: return
        if '/' in node_id:
            fid,nid = node_id.split('/',1)
            if self.project and fid in {entry['id'] for entry in scene_entries(self.project)}:
                if fid!=self.scene_id:
                    if not self.switch_scene(fid): return
                    if self.runtime.active:
                        self.pending_focus=nid
                        self.pending_code_diagnostic=diagnostic
                        return
                self.focus_problem(nid, diagnostic=diagnostic); return
            if fid.isdigit():
                self.edit_function(int(fid),focus=nid,diagnostic=diagnostic)
                return
        self.adapter.focus(node_id)
        if diagnostic:
            node = next((n for n in self.adapter.graph.all_nodes() if n.get_property('stable_id') == node_id), None)
            if node is not None:
                self.edit_node_code(node, diagnostic=diagnostic)

    def build_diagnostic(self, diagnostic):
        item = QListWidgetItem(f"{diagnostic['node']}:{diagnostic['line']}:{diagnostic['column']}: {diagnostic['message']}")
        item.setData(Qt.ItemDataRole.UserRole, diagnostic)
        self.problems.addItem(item)
        self.output_tabs.setCurrentWidget(self.problems)

    def filter_library(self, query):
        for i in range(self.library_tree.topLevelItemCount()):
            root = self.library_tree.topLevelItem(i)
            visible = False
            for j in range(root.childCount()):
                child = root.child(j)
                matches = all(word in child.text(0).lower() for word in query.lower().split())
                child.setHidden(not matches)
                visible |= matches
            root.setHidden(not visible)
            if query:
                root.setExpanded(True)

    def add_library_node(self, item, _column):
        type_id = item.data(0, Qt.ItemDataRole.UserRole)
        if type_id:
            self.adapter.add(type_id)

    def quick_add(self):
        dialog = SearchDialog([(n.name, n.id) for n in self.adapter.suggested_specs()], "Add Node", self,
                              hint='Node Library > Node suggestions controls 2D / 3D suggestions. Port connections require matching types.')
        if dialog.exec() == QDialog.DialogCode.Accepted:
            node = self.adapter.add(dialog.result_value)
            self.adapter.graph.center_on([node])

    def commands(self):
        dialog = SearchDialog([(name, name) for name, action in self.actions.items() if action.isEnabled()],
                              "Command Palette", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.actions[dialog.result_value].trigger()

    def frame_all(self):
        self.adapter.clear_selection()
        self.adapter.graph.fit_to_selection()

    def clear_inspector(self):
        while self.inspector_form.rowCount():
            self.inspector_form.removeRow(0)

    def inspect_node(self, node):
        self.inspected_node = node
        self.hierarchy.blockSignals(True)
        self.hierarchy.clearSelection()
        self.hierarchy.blockSignals(False)
        self.refresh_actions()
        self.clear_inspector()
        spec = self.adapter.registry[node.get_property("type_id")]
        heading = QLabel(f"<b>{spec.name}</b>")
        self.inspector_form.addRow(heading)
        nid = QLabel(node.get_property("stable_id"))
        nid.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        nid.setWordWrap(True)
        self.inspector_form.addRow("ID", nid)
        code_button = QPushButton("View / Edit Node Code…")
        code_button.setAccessibleName(f"View or edit code for {spec.name}")
        code_button.clicked.connect(lambda _checked=False, target=node: self.edit_node_code(target))
        self.inspector_form.addRow(code_button)
        help_button = QPushButton("Node Help / IO / Examples…")
        help_button.setAccessibleName(f"Help for {spec.name}")
        help_button.clicked.connect(lambda _checked=False, target=node: self.show_node_help(target))
        self.inspector_form.addRow(help_button)
        if spec.kind == 'switch':
            from .switches import case_button
            self.inspector_form.addRow(case_button(self.adapter,node,self))
        for p in spec.data_inputs:
            value = node.get_property("value_" + p.name)
            if ((spec.category == 14 and p.name in ('Material', 'Sprite')) or (spec.category == 17 and p.name == 'Sound')
                    or (spec.category == 18 and p.name == 'Template')):
                field = QComboBox()
                field.setAccessibleName(f'{spec.name} {p.name}')
                field.setProperty('domain_property', 'value_' + p.name)
                asset_api = {'Material': material_api, 'Sprite': sprite_api, 'Sound': audio_api, 'Template': ui_api}[p.name]
                for asset in asset_api.scene_assets(self.scene):
                    field.addItem(asset['name'], asset['id'])
                if field.findData(value) < 0:
                    field.addItem('Missing: ' + value, value)
                field.setCurrentIndex(field.findData(value))
                field.activated.connect(lambda _, w=field, n=node, key='value_' + p.name: n.set_property(key, w.currentData()))
                self.inspector_form.addRow(p.name, field)
                continue
            field = QLineEdit(value if p.type in ("string", "entity") else json.dumps(value))
            field.setAccessibleName(f"{spec.name} {p.name}")
            field.setProperty("domain_property", "value_" + p.name)
            field.setToolTip(f"{p.type}; enter JSON for numbers, booleans and vectors")
            if spec.event == 'timer':
                field.setToolTip('Empty: all timer names for this receiver. Otherwise match the exact name.' if p.name == 'Filter'
                                 else 'Entity ID, or empty for scene timers. Set this constant here; data wires are not accepted.')
            elif spec.event == 'input':
                field.setToolTip('Constant exact keyboard button, mouse button or action name. Empty listens to all names of this event kind. Events preserve transition order before On Update.')
            elif spec.event == 'animation_finished':
                field.setToolTip('Empty: all clips. Otherwise match the exact clip name (up to 512 UTF-8 bytes).'
                                 if p.name == 'Clip Filter' else
                                 'Entity ID, or empty for all animated entities. Set this constant here; data wires are not accepted.')
            elif spec.event == 'entity_lifecycle':
                field.setToolTip('Entity ID, or empty for all entities. Runs before deletion, including inactive objects; nested destructive edits wait for this edit to finish. Set this constant here.'
                                 if spec.id == 1009 else 'Entity ID, or empty for all entities. Inactive receivers still receive lifecycle changes. Set this constant here; data wires are not accepted.')
            elif spec.event.startswith('ui_'):
                field.setToolTip('Empty matches every widget/element. Otherwise match the exact ID. Set this constant here.')
            elif spec.category == 5 and p.name == 'Owner':
                field.setToolTip('Entity ID, or empty for scene timers. Each owner has its own timer names.')
            elif spec.id == 5010 and p.name == 'Unscaled':
                field.setToolTip('true: use unscaled frame time, even at Time Scale 0. Editor Pause and inactive owners still suspend the timer.')
            elif spec.event == 'custom':
                field.setToolTip('Entity ID, or empty for scene events. Set this constant here.' if p.name == 'Receiver'
                                 else 'true/false. All handlers for this event and receiver must agree. Subscribe/Unsubscribe changes it at runtime.')
            elif spec.event_id and p.name in ('Recipient','Sender'):
                field.setToolTip('Entity ID, or empty for the scene. Sender is explicit; connect Get Self when needed.')
            def commit(port=p, widget=field, target=node):
                try:
                    value = widget.text() if port.type in ("string", "entity") else json.loads(widget.text())
                    if not literal_valid(value, port.type,getattr(self.adapter.registry,'type_schema',None)):
                        raise ValueError(f"Expected {port.type}")
                    target.set_property("value_" + port.name, value)
                    widget.setStyleSheet("")
                except (ValueError, TypeError) as error:
                    widget.setStyleSheet("border: 1px solid #F37C91;")
                    widget.setToolTip(str(error))
            field.editingFinished.connect(commit)
            self.inspector_form.addRow(p.name, field)

    def edit_node_code(self, node=None, *, diagnostic=None):
        """Open the separate code view for the selected node."""
        node = self.inspected_node if node is None or isinstance(node, bool) else node
        if node is None or node not in self.adapter.graph.all_nodes():
            self.statusBar().showMessage("Select a node first", 2500)
            return False
        spec = self.adapter.registry[node.get_property("type_id")]
        try:
            program = compile_project(self.snapshot_project())
            if 'scenes' in program:
                program = program['scenes'][self.scene_id]
            generated = generated_node_code(program, node.get_property('stable_id'), spec)
        except (ValueError, OSError) as error:
            generated = ('// Generated code requires a valid graph.\n// ' + str(error).replace('\n', '\n// ') + '\n' + default_node_code(spec), 1)
        dialog = NodeCodeDialog(spec, node, self, diagnostic=diagnostic, generated_code=generated)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        node.set_property("embedded_code", dialog.result_code or "")
        self.statusBar().showMessage("Node code updated; Build will validate the native snippet.", 4000)
        return True

    def node_property_changed(self, node, name, value):
        if self.inspected_node is not node:
            return
        for field in self.inspector.findChildren(QComboBox):
            if field.property('domain_property') == name:
                if field.findData(value) < 0: field.addItem('Missing: ' + value, value)
                field.setCurrentIndex(field.findData(value))
        for field in self.inspector.findChildren(QLineEdit):
            if field.property("domain_property") == name:
                field.setText(value if isinstance(value, str) else json.dumps(value))
                field.setStyleSheet("")

    def selected_entity_id(self):
        items = self.hierarchy.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def refresh_hierarchy(self, selection=None, inspect=True):
        self.hierarchy.blockSignals(True)
        self.hierarchy.clear()
        root = QTreeWidgetItem([f"Scene: {self.scene_id}"])
        self.hierarchy.addTopLevelItem(root)
        items = {}
        entities = {e['id']: e for e in self.scene.get('entities', [])}
        for entity in self.scene.get("entities", []):
            active = scene_api.is_active(self.scene, entity['id'], entities)
            item = QTreeWidgetItem([entity.get("name", entity["id"]) + ('' if active else ' [inactive]')])
            item.setToolTip(0, f"Active self: {entity.get('active', True)}\nActive in hierarchy: {active}\nLayer: {entity.get('layer', 0)}")
            item.setData(0, Qt.ItemDataRole.UserRole, entity["id"])
            items[entity['id']] = item
        for entity in self.scene.get('entities', []):
            item = items[entity['id']]
            items.get(entity.get('parent', ''), root).addChild(item)
            item.setExpanded(True)
        if selection in items:
            self.hierarchy.setCurrentItem(items[selection])
        root.setExpanded(True)
        self.hierarchy.blockSignals(False)
        if inspect:
            self.select_entity()
        else:
            self.refresh_actions()

    def select_entity(self):
        eid = self.selected_entity_id()
        entity = next((e for e in self.scene.get("entities", []) if e["id"] == eid), None)
        self.refresh_actions()
        if not entity:
            if self.inspected_node is None:
                self.clear_inspector()
            return
        self.inspected_node = None
        self.adapter.clear_selection()
        self.clear_inspector()
        label = QLabel(eid)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.inspector_form.addRow("Stable ID", label)
        for record in self.scene.get('prefab_instances', []):
            local = next((key for key, sid in record['mapping'].items() if sid == eid), None)
            if local is not None:
                asset = next(a for a in self.scene['prefab_assets'] if a['id'] == record['prefab'])
                prefab_label = QLabel(f"{asset['name']} / {local}")
                prefab_label.setWordWrap(True)
                prefab_label.setAccessibleName(f'{eid} prefab')
                self.inspector_form.addRow('Prefab', prefab_label)
                break
        parent = QComboBox()
        parent.setAccessibleName(f'{eid} parent')
        parent.addItem('Scene root', '')
        excluded = {eid} | scene_api.descendant_ids(self.scene, eid)
        for item in self.scene['entities']:
            if item['id'] not in excluded:
                parent.addItem(f'{item.get("name", item["id"])} ({item["id"]})', item['id'])
        parent.setCurrentIndex(parent.findData(entity.get('parent', '')))
        parent.currentIndexChanged.connect(lambda: self.commit_entity_property(eid, 'parent', parent.currentData()))
        self.inspector_form.addRow('Parent', parent)
        visible = QCheckBox('Visible (inherits parent)')
        visible.setAccessibleName(f'{eid} visible')
        visible.setChecked(entity.get('visible', True))
        visible.toggled.connect(lambda value: self.commit_entity_property(eid, 'visible', value))
        self.inspector_form.addRow(visible)
        active = QCheckBox('Active (inherits parent)')
        active.setAccessibleName(f'{eid} active')
        active.setChecked(entity.get('active', True))
        active.toggled.connect(lambda value: self.commit_entity_property(eid, 'active', value))
        self.inspector_form.addRow(active)
        layer = QSpinBox()
        layer.setAccessibleName(f'{eid} layer')
        layer.setKeyboardTracking(False)
        layer.setRange(0, 31)
        layer.setValue(entity.get('layer', 0))
        layer.valueChanged.connect(lambda value: self.commit_entity_property(eid, 'layer', value))
        self.inspector_form.addRow('Layer', layer)
        for key in ("name", "position", "rotation", "scale", "tags"):
            field = QLineEdit(entity.get('name',eid) if key == 'name' else json.dumps(entity.get(key, []), ensure_ascii=False))
            field.setAccessibleName(f"{eid} {key}")
            def commit(prop=key, widget=field):
                try:
                    value = widget.text().strip() if prop == 'name' else json.loads(widget.text())
                    widget.setStyleSheet("")
                    self.commit_entity_property(eid, prop, value)
                except (ValueError, TypeError) as error:
                    widget.setStyleSheet("border: 1px solid #F37C91;")
                    widget.setToolTip(str(error))
            field.editingFinished.connect(commit)
            self.inspector_form.addRow(key.title(), field)
        if entity.get("mesh"):
            label = QLabel(entity["mesh"])
            label.setWordWrap(True)
            self.inspector_form.addRow("Mesh", label)
            remove = QPushButton("Remove Mesh")
            remove.clicked.connect(lambda: self.push_scene("Remove mesh",scene_api.set_entity_property(self.scene,eid,'mesh',None),eid))
            self.inspector_form.addRow(remove)

        sprite_binding = entity.get('sprite')
        sprite = QComboBox(); sprite.setAccessibleName(f'{eid} sprite'); sprite.addItem('None', '')
        sprite_assets = sprite_api.scene_assets(self.scene)
        for asset in sprite_assets: sprite.addItem(asset['name'], asset['id'])
        sprite.setCurrentIndex(sprite.findData(sprite_binding['asset'] if sprite_binding else ''))
        def assign_sprite(_):
            sid = sprite.currentData()
            QTimer.singleShot(0, lambda: self.set_entity_sprite(eid, sprite_api.binding(sid)))
        sprite.activated.connect(assign_sprite); self.inspector_form.addRow('Sprite', sprite)
        if sprite_binding:
            asset = next(a for a in sprite_assets if a['id'] == sprite_binding['asset'])
            frame = QSpinBox(); frame.setRange(0, asset['columns'] * asset['rows'] - 1)
            frame.setValue(sprite_binding['frame']); frame.setAccessibleName(f'{eid} sprite frame')
            def update_sprite(key, value):
                current = deepcopy(scene_api.entity(self.scene, eid)['sprite']); current[key] = value
                QTimer.singleShot(0, lambda: self.set_entity_sprite(eid, current))
            frame.editingFinished.connect(lambda: update_sprite('frame', frame.value()))
            self.inspector_form.addRow('Sprite frame', frame)
            for key, label in [('flip_x', 'Flip X'), ('flip_y', 'Flip Y')]:
                flag = QCheckBox(label); flag.setChecked(sprite_binding[key]); flag.setAccessibleName(f'{eid} sprite {key}')
                flag.clicked.connect(lambda value, k=key: update_sprite(k, value)); self.inspector_form.addRow(flag)

        binding = entity.get('material')
        material = QComboBox()
        material.setAccessibleName(f'{eid} material')
        material.addItem('Imported mesh material', '')
        for asset in material_api.scene_assets(self.scene):
            material.addItem(asset['name'], asset['id'])
        material.setCurrentIndex(material.findData(binding['asset'] if binding else ''))
        def assign_material(_):
            mid = material.currentData()
            # Rebuild the Inspector after the combo's activation has completed.
            QTimer.singleShot(0, lambda: self.assign_material(eid, mid))
        material.activated.connect(assign_material)
        self.inspector_form.addRow('Material', material)
        if binding:
            edit = QPushButton('Edit Material Instance…')
            edit.clicked.connect(lambda: self.edit_entity_material(eid))
            self.inspector_form.addRow(edit)
            reset = QPushButton('Reset Material Parameters')
            reset.setEnabled(bool(binding['overrides']))
            reset.clicked.connect(lambda: self.assign_material(eid, binding['asset']))
            self.inspector_form.addRow(reset)

        body = entity.get('rigid_body')
        if body:
            self.inspector_form.addRow('Rigid Body', QLabel(('Character · ' if 'character' in body else '')+f"{body['shape']} · {body['motion']}"))
        edit_body = QPushButton('Edit Rigid Body…' if body else 'Add Rigid Body…')
        edit_body.setAccessibleName(f'{eid} rigid body settings')
        edit_body.clicked.connect(lambda: self.edit_rigid_body(eid))
        self.inspector_form.addRow(edit_body)
        if body:
            remove_body = QPushButton('Remove Rigid Body')
            remove_body.clicked.connect(lambda: QTimer.singleShot(0, lambda: self.push_scene('Remove rigid body',
                scene_api.set_entity_property(self.scene, eid, 'rigid_body', None), eid)))
            self.inspector_form.addRow(remove_body)

        if entity.get('camera') is not None:
            lens = entity['camera']
            self.inspector_form.addRow('Camera', QLabel(f"{lens['projection']} · FOV {lens['fov']:g}° · height {lens['size']:g}"))
            edit = QPushButton('Edit Camera…')
            edit.clicked.connect(lambda: self.edit_camera(eid))
            self.inspector_form.addRow(edit)
            activate = QPushButton('Use as Game Camera')
            activate.setEnabled(self.scene.get('active_camera') != eid)
            activate.clicked.connect(lambda: self.push_scene('Select active camera', camera_api.set_active_camera(self.scene, eid), eid))
            self.inspector_form.addRow(activate)

        schemas = {str(d['id']): d for d in self.scene.get('component_definitions', [])}
        for key, instance in entity.get('components', {}).items():
            schema = schemas[key]
            cid = schema['id']
            self.inspector_form.addRow(QLabel(schema['name']))
            enabled = QCheckBox('Enabled')
            enabled.setAccessibleName(f'{eid} component {cid} enabled')
            enabled.setChecked(instance.get('enabled', True))
            enabled.toggled.connect(lambda value, c=cid: self.commit_component(eid, c, 'enable', value))
            self.inspector_form.addRow(enabled)
            for prop in schema['properties']:
                pid = prop['id']
                value = instance.get('properties', {}).get(str(pid), prop.get('default', default_value(prop['type'])))
                field = QLineEdit(json.dumps(value, ensure_ascii=False))
                field.setAccessibleName(f'{eid} component {cid} property {pid}')
                field.setToolTip(f"{prop['type']} (JSON)")
                def commit_property(c=cid, p=pid, widget=field):
                    try:
                        self.commit_component(eid, c, 'set', json.loads(widget.text()), p)
                        widget.setStyleSheet('')
                    except (ValueError, TypeError) as error:
                        widget.setStyleSheet('border: 1px solid #F37C91;')
                        widget.setToolTip(str(error))
                field.editingFinished.connect(commit_property)
                self.inspector_form.addRow(prop['name'], field)
            remove = QPushButton('Remove '+schema['name'])
            remove.setAccessibleName(f'{eid} component {cid} remove')
            remove.clicked.connect(lambda _, c=cid: self.commit_component(eid, c, 'remove'))
            self.inspector_form.addRow(remove)
        add = QPushButton('Add Component…')
        add.setEnabled(self.actions['Add Component…'].isEnabled())
        add.clicked.connect(self.add_component)
        self.inspector_form.addRow(add)

    def commit_entity_property(self, eid, prop, value):
        after = scene_api.set_entity_property(self.scene, eid, prop, value)
        # Keep the editing widget alive through its key/mouse event. Undo/Redo
        # and external changes still rebuild the Inspector from the document.
        previous = getattr(self, '_preserve_entity_fields', False)
        self._preserve_entity_fields = True
        try:
            self.push_scene(f'Set {prop}', after, eid)
        finally:
            self._preserve_entity_fields = previous

    def push_scene(self, label, after, selection=None):
        if after != self.scene:
            self.adapter.graph.undo_stack().push(SceneCommand(self, label, after, selection))

    def apply_scene(self, scene, selection):
        before = self.scene
        self.scene = deepcopy(scene)
        if before.get('component_definitions', []) != scene.get('component_definitions', []):
            self.adapter.configure_components(scene.get('component_definitions', []))
            self.refresh_library()
        self.refresh_hierarchy(selection, inspect=not getattr(self, '_preserve_entity_fields', False))
        self.document_changed()
        if not self.runtime.ready:
            return
        old = {e['id']:e for e in before['entities']}
        new = {e['id']:e for e in scene['entities']}
        try:
            transforms = {'position', 'rotation', 'scale'}
            if (self.runtime_scene in (None,self.scene_id) and before['variables'] == scene['variables'] and before.get('prefab_assets', []) == scene.get('prefab_assets', []) and
                    before.get('input') == scene.get('input') and
                    before.get('material_assets', []) == scene.get('material_assets', []) and
                    before.get('sprite_assets', []) == scene.get('sprite_assets', []) and
                    before.get('audio_assets', []) == scene.get('audio_assets', []) and
                    before.get('ui_assets', []) == scene.get('ui_assets', []) and
                    before.get('active_camera') == scene.get('active_camera') and
                    before.get('prefab_instances', []) == scene.get('prefab_instances', []) and
                    before.get('component_definitions', []) == scene.get('component_definitions', []) and old.keys() == new.keys() and all(
                    {p:v for p,v in old[k].items() if p not in transforms} ==
                    {p:v for p,v in new[k].items() if p not in transforms} for k in old)):
                for eid, entity in new.items():
                    for prop in ('position','rotation','scale'):
                        if entity[prop] != old[eid][prop]:
                            self.runtime.send('set_property',entity=eid,property=prop,value=entity[prop])
            else:
                running = self.runtime.state == 'running'
                self.reload_preview(compile_project(self.snapshot_project(preview=True,scene=scene)),running)
                self.console.appendPlainText('Scene structure changed; requesting a preview reset.')
        except (ValueError, RuntimeError) as error:
            self.console.appendPlainText(f'Scene edited; preview refresh failed: {error}')

    def create_entity(self, _checked=False):
        if self.project_path:
            after, eid = scene_api.create_entity(self.scene)
            self.push_scene('Create entity',after,eid)

    def create_camera(self, _checked=False):
        if self.project_path:
            after, eid = camera_api.create_camera(self.scene)
            self.push_scene('Create camera', after, eid)

    def edit_ui_library(self):
        if not self.project_path: return
        dialog = UiLibraryDialog(self.scene, self.project_path.parent, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Edit UI templates', dialog.result_scene, self.selected_entity_id())
        dialog.deleteLater()

    def edit_sound_library(self):
        if not self.project_path: return
        dialog = SoundLibraryDialog(self.scene, self.project_path.parent, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Edit sound library', dialog.result_scene, self.selected_entity_id())
            self.refresh_assets()
        dialog.deleteLater()

    def edit_sprite_library(self):
        if not self.project_path: return
        dialog = SpriteLibraryDialog(self.scene, self.project_path.parent, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Edit sprite library', dialog.result_scene, self.selected_entity_id())
            self.refresh_assets()

    def set_entity_sprite(self, eid, binding):
        self.push_scene('Edit sprite', scene_api.set_entity_property(self.scene, eid, 'sprite', binding), eid)

    def edit_material_library(self):
        if not self.project_path: return
        dialog = MaterialLibraryDialog(self.scene, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Edit material library', dialog.result_scene, self.selected_entity_id())
        dialog.deleteLater()

    def assign_material(self, eid, mid):
        binding = {'asset': mid, 'overrides': {}} if mid else None
        self.push_scene('Assign material', scene_api.set_entity_property(self.scene, eid, 'material', binding), eid)

    def edit_entity_material(self, eid):
        binding = scene_api.entity(self.scene, eid)['material']
        before = material_api.effective_parameters(self.scene, binding)
        dialog = MaterialParametersDialog(before, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            after = deepcopy(binding)
            after['overrides'].update({k: v for k, v in dialog.result_parameters.items() if v != before[k]})
            self.push_scene('Edit material instance', scene_api.set_entity_property(self.scene, eid, 'material', after), eid)
        dialog.deleteLater()

    def edit_rigid_body(self, eid):
        dialog = RigidBodyDialog(scene_api.entity(self.scene, eid).get('rigid_body'), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.push_scene('Edit rigid body', scene_api.set_entity_property(
                    self.scene, eid, 'rigid_body', dialog.result_body), eid)
            except ValueError as error:
                QMessageBox.warning(self, 'Cannot edit rigid body', str(error))
        dialog.deleteLater()

    def edit_camera(self, eid):
        dialog = CameraDialog(scene_api.entity(self.scene, eid)['camera'], self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Edit camera', scene_api.set_entity_property(self.scene, eid, 'camera', dialog.result_camera), eid)
        dialog.deleteLater()

    def choose_camera(self):
        if not self.project_path:
            return
        options = [('No game camera (editor orbit)', '')] + [
            (f"{e.get('name', e['id'])} ({e['id']})", e['id'])
            for e in self.scene['entities'] if e.get('camera') is not None]
        dialog = SearchDialog(options, 'Choose Active Camera', self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.push_scene('Select active camera', camera_api.set_active_camera(self.scene, dialog.result_value), self.selected_entity_id())
        dialog.deleteLater()

    def view_game_camera(self, checked):
        if self.runtime.ready:
            self.runtime.send('view_camera', game=checked)

    def edit_variables(self):
        if not self.project_path:
            return
        from editor.core.typed_schema import build_schema
        from editor.core.user_collections import is_user_collection
        schema = getattr(self.adapter.registry, 'type_schema', None) or build_schema(
            self.scene.get('struct_definitions', []), self.scene.get('enum_definitions', []))
        dialog = VariablesDialog(self.scene['variables'], self, scopes=self.scene.get('variable_scopes', {}), schema=schema)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            after = deepcopy(self.scene)
            after['variables'] = dialog.result_variables
            if any(isinstance(v, dict) and (v.get('type', '').startswith(('struct:', 'enum:')) or is_user_collection(v.get('type')))
                   for v in after['variables'].values()):
                # Scene documents must also validate independently of their graph.
                after['struct_definitions'] = deepcopy(list(schema.structs.values()))
                after['enum_definitions'] = deepcopy(list(schema.enums.values()))
            if dialog.result_scopes:
                after['variable_scopes'] = dialog.result_scopes
            else:
                after.pop('variable_scopes', None)
            self.push_scene('Edit scene variables', scene_api.validate_scene(after), self.selected_entity_id())

    def edit_input(self):
        if not self.project_path:
            return
        dialog = InputDialog(self.scene.get('input', empty_input()), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            after = deepcopy(self.scene)
            after['input'] = dialog.result_input
            self.push_scene('Edit input bindings', scene_api.validate_scene(after), self.selected_entity_id())

    def create_prefab(self):
        if eid := self.selected_entity_id():
            name, okay = QInputDialog.getText(self, 'Create Prefab', 'Prefab name',
                                             text=scene_api.entity(self.scene, eid).get('name', eid))
            if not okay or not name.strip():
                return
            try:
                after, _ = add_scene_prefab(self.scene, eid, name.strip())
                self.push_scene('Create prefab', after, eid)
            except ValueError as error:
                QMessageBox.warning(self, 'Cannot create prefab', str(error))

    def instantiate_prefab(self):
        assets = self.scene.get('prefab_assets', [])
        dialog = SearchDialog([(f"{a['name']} ({a['id']})", a['id']) for a in assets], 'Instantiate Prefab', self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_value:
            try:
                after, root = instantiate_scene_prefab(self.scene, dialog.result_value)
                self.push_scene('Instantiate prefab', after, root)
            except ValueError as error:
                QMessageBox.warning(self, 'Cannot instantiate prefab', str(error))

    def duplicate_entity(self):
        if eid := self.selected_entity_id():
            after, new_id = scene_api.duplicate_entity(self.scene,eid)
            self.push_scene('Duplicate entity',after,new_id)

    def apply_prefab(self):
        if eid := self.selected_entity_id():
            try:
                self.push_scene('Apply prefab overrides', apply_prefab_overrides(self.scene, eid), eid)
            except ValueError as error:
                QMessageBox.warning(self, 'Cannot apply prefab overrides', str(error))

    def reset_prefab(self):
        if eid := self.selected_entity_id():
            answer = QMessageBox.question(self, 'Reset Prefab Instance',
                'Restore this entire instance from its prefab? Added children will be removed and deleted '
                'members restored. The root placement is kept. You can undo this change.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                self.push_scene('Reset prefab instance', reset_prefab_instance(self.scene, eid), eid)
            except ValueError as error:
                QMessageBox.warning(self, 'Cannot reset prefab instance', str(error))

    def delete_entity(self):
        if eid := self.selected_entity_id():
            self.push_scene('Delete entity',scene_api.delete_entity(self.scene,eid))

    def rename_entity(self):
        if eid := self.selected_entity_id():
            name, okay = QInputDialog.getText(self,'Rename Entity','Name',text=scene_api.entity(self.scene,eid).get('name',eid))
            if okay and name.strip():
                self.push_scene('Rename entity',scene_api.set_entity_property(self.scene,eid,'name',name.strip()),eid)

    def entity_menu(self, point):
        item = self.hierarchy.itemAt(point)
        if item:
            self.hierarchy.setCurrentItem(item)
        menu = QMenu(self)
        for name in ('Create Entity','Duplicate Entity','Rename Entity…','Delete Entity',
                     'Create Prefab from Entity…','Instantiate Prefab…',
                     'Apply Prefab Overrides','Reset Prefab Instance…'):
            menu.addAction(self.actions[name])
        menu.exec(self.hierarchy.viewport().mapToGlobal(point))

    def refresh_assets(self):
        self.assets.clear()
        if self.project_path:
            for path in sorted((self.project_path.parent / "assets").rglob("*")):
                if path.is_file():
                    relative = path.relative_to(self.project_path.parent).as_posix()
                    item = QListWidgetItem(f"{path.suffix[1:].upper()}   {relative[7:]}   ·   {path.stat().st_size:,} bytes")
                    item.setData(Qt.ItemDataRole.UserRole, relative)
                    item.setToolTip('Double click glTF/GLB to create an entity')
                    self.assets.addItem(item)

    def instantiate_asset(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and Path(path).suffix.lower() in ('.glb','.gltf'):
            after, eid = scene_api.create_entity(self.scene,Path(path).stem,path)
            self.push_scene('Create entity from asset',after,eid)

    def import_model(self):
        if not self.project_path:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import Model", str(self.project_path.parent), "glTF Models (*.gltf *.glb)")
        if not path:
            return
        try:
            relative = copy_model(path,self.project_path.parent)
            if relative not in self.project.setdefault('assets',[]):
                self.project['assets'].append(relative)
            if eid := self.selected_entity_id():
                after = scene_api.set_entity_property(self.scene,eid,'mesh',relative)
            else:
                after, eid = scene_api.create_entity(self.scene,Path(path).stem,relative)
            self.push_scene('Assign imported mesh',after,eid)
            self.refresh_assets()
            self.document_changed()
            self.console.appendPlainText(f"Imported {relative}; native geometry validation runs when preview starts.")
        except Exception as error:
            self.console.appendPlainText(f"Import failed: {error}")

    def import_prefab_library(self):
        if not self.project_path or self.builder.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Import Prefab Library',
            str(self.project_path.parent.parent), PROJECT_FILTER)
        if not path:
            return
        try:
            count = len(self.scene.get('prefab_assets', []))
            after = import_project_prefabs(self.scene, self.project_path.parent, path)
            self.push_scene('Import prefab library', after, self.selected_entity_id())
            self.refresh_assets()
            self.console.appendPlainText(f"Imported {len(after['prefab_assets']) - count} prefabs from {Path(path).parent.name}. Save to keep the library in this project.")
        except Exception as error:
            self.console.appendPlainText(f'Prefab library import failed: {error}')

    def register_prefabs(self):
        if not self.project_path or self.builder.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, 'Register Prefab Files',
            str(self.project_path.parent / 'assets'), 'Prefab Assets (*.prefab.json)')
        if not paths:
            return
        try:
            after = register_prefab_files(self.scene, self.project_path.parent, paths)
            self.push_scene('Register prefab files', after, self.selected_entity_id())
            self.console.appendPlainText(f'Registered {len(paths)} prefabs. Save to keep this library snapshot; file edits are not watched.')
        except Exception as error:
            self.console.appendPlainText(f'Prefab registration failed: {error}')

    def validate_graph(self):
        try:
            compile_project(self.snapshot_project()) if self.project_path else compile_graph(self.adapter.document(),self.scene or None)
            errors = []
        except GraphError as error:
            errors = error.problems
        except (ValueError,OSError) as error:
            errors = [Problem('scene', str(error))]
        self.problems.clear()
        for p in errors:
            item = QListWidgetItem(f"{p.node}: {p.message}")
            item.setData(Qt.ItemDataRole.UserRole, p.node)
            self.problems.addItem(item)
        self.statusBar().showMessage(f"{len(errors)} graph problems" if errors else "Graph valid", 4000)
        if errors:
            self.output_tabs.setCurrentWidget(self.problems)
        return not errors

    def export_cpp(self):
        if not self.project_path or not self.validate_graph():
            return
        try:
            path = export(compile_project(self.snapshot_project()), self.project_path.parent / "generated")
            self.console.appendPlainText(f"Generated {path}")
        except Exception as error:
            self.console.appendPlainText(str(error))

    def build_game(self):
        if not self.project_path or not self.validate_graph() or self.builder.busy:
            return
        if self.runtime.active:
            self.pending_build = True
            self.runtime.shutdown()
            return
        self.build_output.clear()
        self.output_tabs.setCurrentWidget(self.build_output)
        try:
            self.builder.start(self.project_path, self.adapter.document(), deepcopy(self.scene),snapshot=self.snapshot_project())
        except (OSError,ValueError) as error:
            self.console.appendPlainText(f'Build failed: {error}')

    def build_finished(self, success):
        self.statusBar().showMessage("Build succeeded" if success else "Build failed or cancelled", 7000)
        self.refresh_actions()
        if success and self.pending_play:
            self.pending_play = False
            self.play()
        elif not success:
            self.pending_play = False

    def preview_executable(self, ir=None):
        local = self.project_path.parent / "build/node_view.exe"
        if os.name != "nt":
            local = local.with_suffix("")
        expected = runtime_fingerprint()
        code_source = generate_node_code(ir) if ir is not None else ''
        code_hash = hashlib.sha256(code_source.encode('utf-8')).hexdigest() if 'rt::RegisterNodeCode(' in code_source else None
        shared = ROOT / 'build' / local.name
        for candidate in ((local,) if code_hash else (local,shared)):
            if runtime_current(candidate,expected,node_code=code_hash):
                return candidate
        return None

    def play(self):
        if not self.project_path or not self.validate_graph():
            return
        try:
            ir = compile_project(self.snapshot_project(preview=True))
            exe = self.preview_executable(ir)
            if exe is None:
                self.console.appendPlainText('Building the native runtime and embedded code for this project…')
                self.pending_play = True
                self.build_game()
                return
            if self.runtime.ready:
                if self.runtime.state == "paused":
                    self.runtime.send("play")
                else:
                    self.reload_preview(ir,True)
                return
            if self.runtime.active:
                return
            path = self.project_path.parent / "generated/preview.ir.json"
            save_json(path, ir)
            self.runtime.start(exe, path, self.project_path.parent)
            self.statusBar().showMessage("Starting native runtime…")
        except Exception as error:
            self.console.appendPlainText(f"Preview failed: {error}")

    def runtime_connected(self):
        self.view_game_camera(self.actions['Game Camera'].isChecked())
        self.runtime.send("play")

    def reload_preview(self, ir, resume):
        if 'rt::RegisterNodeCode(' in generate_node_code(ir) and self.preview_executable(ir) is None:
            self.pending_play = resume
            self.console.appendPlainText('Embedded code or native sources changed; rebuilding Preview…')
            self.build_game()
            return
        self.reload_request = (self.runtime.send('load_ir',ir=ir),resume)

    def pause(self):
        if self.runtime.ready:
            self.runtime.send("pause")

    def stop(self):
        if self.runtime.ready:
            self.runtime.send("stop")

    def runtime_message(self, message):
        event = message.get("event")
        if self.reload_request and message.get('id') == self.reload_request[0]:
            if event == 'ack':
                _, resume = self.reload_request
                self.reload_request = None
                if resume:
                    self.runtime.send('play')
            elif event == 'node_error':
                self.reload_request = None
        if event == "window_handle" and os.name == "nt":
            try:
                self.foreign_window = QWindow.fromWinId(message["handle"])
                self.container = QWidget.createWindowContainer(self.foreign_window, self.viewport)
                self.container.setMinimumSize(240, 220)
                self.viewport_hint.hide()
                self.viewport_layout.addWidget(self.container, 1)
            except Exception as error:
                self.console.appendPlainText(f"Native embedding unavailable; use separate Game View: {error}")
        elif event == "release_focus":
            if os.name == 'nt':
                # The foreign SDL child owns native focus even when Qt's focusWidget is unchanged.
                import ctypes
                ctypes.windll.user32.SetFocus(ctypes.c_void_p(int(self.winId())))
            self.adapter.graph.viewer().setFocus()
        elif event == "state":
            self.statusBar().showMessage(f"Runtime: {message['state']}")
        elif event == "metrics":
            self.metrics.setText(f"Frame {message['frame']}  ·  {message['frame_ms']:.1f} ms  ·  {message['entities']} entities")
        elif event in ('scene_loaded','scene_changed','scene_restored'):
            self.runtime_scene=message.get('scene',self.scene_id)
            self.console.appendPlainText(f"Runtime scene: {self.runtime_scene}")
        elif event in ("log", "node_error"):
            self.console.appendPlainText(message.get("message", ""))
            if event == "node_error":
                node=message.get('node') or 'Runtime'
                if message.get('scene'): node=message['scene']+'/'+node
                item = QListWidgetItem(f"{node}: {message['message']}")
                item.setData(Qt.ItemDataRole.UserRole, node)
                self.problems.addItem(item)
                self.output_tabs.setCurrentWidget(self.problems)
        elif event in ("hello", "asset_loaded"):
            self.console.appendPlainText(json.dumps(message))
        self.refresh_actions()

    def runtime_stopped(self, code):
        self.reload_request = None
        self.runtime_scene = None
        if self.container:
            self.container.setParent(None)
            self.container.deleteLater()
            self.container = None
            self.foreign_window = None
        self.viewport_hint.show()
        self.metrics.clear()
        self.console.appendPlainText(f"Runtime exited with code {code}. Graph is preserved.")
        self.refresh_actions()
        if self.pending_project:
            path, self.pending_project = self.pending_project, None
            self.open_project(path)
        if self.pending_scene:
            scene_id,self.pending_scene=self.pending_scene,None
            self.open_project(self.project_path,scene_id)
            if self.pending_focus:
                node,self.pending_focus=self.pending_focus,None
                diagnostic = getattr(self, 'pending_code_diagnostic', None)
                self.pending_code_diagnostic = None
                self.focus_problem(node, diagnostic=diagnostic)
        if self.pending_build:
            self.pending_build = False
            self.build_game()
        if self.closing:
            self.close()

    def run_built(self):
        if not self.project_path:
            return
        exe = self.project_path.parent / "build" / ("node_game_view.exe" if os.name == "nt" else "node_game_view")
        if not exe.exists():
            self.console.appendPlainText("Build the project first.")
            return
        subprocess_args = [str(exe), "--project-root", str(exe.parent)]
        from PySide6.QtCore import QProcess
        QProcess.startDetached(subprocess_args[0], subprocess_args[1:], str(exe.parent))

    def refresh_actions(self, *_):
        if not self.actions:
            return
        self.actions['Project Markdown…'].setEnabled(self.project_path is not None)
        self.actions["Build Game"].setEnabled(not self.builder.busy)
        self.actions["Cancel Build"].setEnabled(self.builder.busy)
        self.actions["Play"].setEnabled(not self.builder.busy)
        self.actions["Pause"].setEnabled(self.runtime.ready and self.runtime.state == "running")
        self.actions["Stop"].setEnabled(self.runtime.ready and self.runtime.state != "stopped")
        stack = self.adapter.graph.undo_stack()
        if not isValid(stack):
            return
        self.actions['Undo'].setEnabled(stack.canUndo())
        self.actions['Redo'].setEnabled(stack.canRedo())
        self.actions['New Project…'].setEnabled(not self.builder.busy)
        self.actions['Open Project…'].setEnabled(not self.builder.busy)
        self.actions['Project Manager…'].setEnabled(not self.builder.busy)
        self.actions['Convert to .nen…'].setEnabled(self.project_path is not None and self.project_path.suffix.lower()!='.nen' and not self.builder.busy and not self.runtime.active)
        for label in ('Import Prefab Library…', 'Register Prefab Files…'):
            self.actions[label].setEnabled(self.project_path is not None and not self.builder.busy)
        for label in ('New Scene…','Choose Scene…'):
            self.actions[label].setEnabled(self.project_path is not None and not self.builder.busy)
        self.actions['Use as Startup Scene'].setEnabled(self.project.get('version')==2 and
            self.project.get('entry_scene')!=self.scene_id and not self.builder.busy)
        self.actions['Create Entity'].setEnabled(self.project_path is not None)
        self.actions['Create Camera'].setEnabled(self.project_path is not None)
        self.actions['Choose Active Camera…'].setEnabled(self.project_path is not None)
        self.actions['View/Edit Node Code…'].setEnabled(bool(self.adapter.graph.selected_nodes()))
        self.actions['Instantiate Prefab…'].setEnabled(bool(self.scene.get('prefab_assets')))
        self.actions['Create Prefab from Entity…'].setEnabled(self.selected_entity_id() is not None)
        self.actions['Scene Variables…'].setEnabled(self.project_path is not None)
        self.actions['Structs and Enums…'].setEnabled(self.project_path is not None and not self.builder.busy)
        self.actions['Input Actions and Axes…'].setEnabled(self.project_path is not None)
        self.actions['Materials…'].setEnabled(self.project_path is not None)
        self.actions['Sprites…'].setEnabled(self.project_path is not None)
        self.actions['Sounds…'].setEnabled(self.project_path is not None)
        self.actions['New Function…'].setEnabled(self.project_path is not None)
        self.actions['Define Event…'].setEnabled(self.project_path is not None)
        self.actions['Define Component…'].setEnabled(self.project_path is not None)
        eid = self.selected_entity_id()
        is_instance = any(eid in r['mapping'].values() for r in self.scene.get('prefab_instances', []))
        self.actions['Apply Prefab Overrides'].setEnabled(is_instance)
        self.actions['Reset Prefab Instance…'].setEnabled(is_instance)
        attached = scene_api.entity(self.scene, eid).get('components', {}) if eid else {}
        self.actions['Add Component…'].setEnabled(bool(eid) and any(
            str(d['id']) not in attached for d in self.scene.get('component_definitions', [])))
        self.actions['Edit Function…'].setEnabled(bool(self.adapter.functions))
        self.actions['Edit Function Signature…'].setEnabled(bool(self.adapter.functions) and not self.builder.busy)
        self.actions['Edit Event Signature…'].setEnabled(bool(self.adapter.event_definitions) and not self.builder.busy)
        self.actions['Extract Function…'].setEnabled(self.project_path is not None and not self.builder.busy)
        for name in ('Duplicate Entity','Rename Entity…','Delete Entity'):
            self.actions[name].setEnabled(self.selected_entity_id() is not None)

    def switch_workspace(self, index):
        if not hasattr(self, "splitter"):
            return
        name = self.workspace.tabText(index)
        self.splitter.setSizes([300, 800] if name == "Layout" else [800, 400])
        if name == "Debug":
            self.output_tabs.setCurrentWidget(self.console)
            self.docks["OutputDock"].show()

    def save_layout(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("docks-v1", self.saveState(1))
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("workspace", self.workspace.currentIndex())
        self.settings.sync()

    def restore_layout(self):
        if geometry := self.settings.value("geometry"):
            self.restoreGeometry(geometry)
        if state := self.settings.value("docks-v1"):
            self.restoreState(state, 1)
        self.workspace.setCurrentIndex(int(self.settings.value("workspace", 1)))
        if state := self.settings.value("splitter"):
            self.splitter.restoreState(state)

    def reset_layout(self):
        for name, dock in self.docks.items():
            dock.setFloating(False)
            area = Qt.DockWidgetArea.RightDockWidgetArea if name == "InspectorDock" else (
                Qt.DockWidgetArea.BottomDockWidgetArea if name == "OutputDock" else Qt.DockWidgetArea.LeftDockWidgetArea)
            self.addDockWidget(area, dock)
            dock.show()
        self.splitter.setSizes([680, 500])

    def closeEvent(self, event):
        if not self.closing and not self.confirm_unsaved():
            event.ignore()
            return
        if self.builder.busy:
            QMessageBox.information(self, "Build running", "Cancel the current build before closing.")
            event.ignore()
            return
        self.save_layout()
        if self.runtime.active:
            self.closing = True
            self.runtime.shutdown()
            event.ignore()
            return
        event.accept()
