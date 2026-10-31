"""Scene edits share the graph's undo stack and update the one domain document."""
from copy import deepcopy
from PySide6.QtGui import QUndoCommand


class SceneCommand(QUndoCommand):
    def __init__(self, window, label, after, selection=None):
        super().__init__(label)
        self.window = window
        self.before, self.after = deepcopy(window.scene), deepcopy(after)
        self.before_selection, self.after_selection = window.selected_entity_id(), selection

    def redo(self):
        self.window.apply_scene(self.after, self.after_selection)

    def undo(self):
        self.window.apply_scene(self.before, self.before_selection)
