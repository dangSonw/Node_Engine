COLORS = {
    "canvas": "#0B0F15", "app": "#10141B", "panel": "#171C25",
    "raised": "#232B38", "hover": "#2A3443", "border": "#303947",
    "text": "#F0F3F9", "secondary": "#ADB8C9", "muted": "#8492A6",
    "accent": "#A78BFA", "cyan": "#5DD6E8", "error": "#F37C91",
}
class PinColors(dict):
    def __missing__(self, key):
        if key.startswith(('array<','map<','set<')) and key.endswith('>'):
            return self[key[key.index('<')+1:-1]]
        if key.startswith('struct:'):
            return (166, 129, 211)
        if key.startswith('enum:'):
            return (230, 161, 208)
        raise KeyError(key)


PIN_COLORS = PinColors({"exec": (221, 227, 238), "bool": (240, 128, 147),
              "float": (143, 215, 156), "int": (102, 205, 181), "string": (230, 161, 208),
              "vec2": (220, 182, 116), "vec3": (233, 200, 121),
              "vec4": (246, 166, 116), "quat": (195, 145, 235),
              "mat4": (166, 129, 211), "entity": (105, 172, 239)})
for _kind in ('array', 'map', 'set'):
    for _type in ('float', 'int', 'bool', 'string', 'vec2', 'vec3', 'vec4', 'quat', 'mat4', 'entity'):
        PIN_COLORS[f'{_kind}<{_type}>'] = PIN_COLORS[_type]


def stylesheet():
    c = COLORS
    return f"""
    QWidget {{ color: {c['text']}; background: {c['panel']}; font-family: 'Segoe UI'; font-size: 12px; }}
    QMainWindow, QMenuBar, QStatusBar {{ background: {c['app']}; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {c['hover']}; }}
    QDockWidget::title {{ background: {c['raised']}; padding: 7px; font-weight: 600; }}
    QToolBar {{ background: {c['app']}; spacing: 6px; padding: 6px; border: 0; }}
    QToolButton, QPushButton {{ background: {c['raised']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 5px 9px; }}
    QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; }}
    QPushButton:disabled, QToolButton:disabled {{ color: {c['muted']}; }}
    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{ background: {c['app']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 5px; min-height: 18px; }}
    QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {c['accent']}; }}
    QTreeWidget, QListWidget, QPlainTextEdit {{ background: {c['canvas']}; border: 0; }}
    QTreeWidget::item, QListWidget::item {{ padding: 5px 3px; }}
    QTreeWidget::item:selected, QListWidget::item:selected {{ background: #3C3554; }}
    QTabBar::tab {{ background: {c['app']}; padding: 8px 14px; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ color: {c['accent']}; border-bottom: 2px solid {c['accent']}; }}
    QTabWidget::pane {{ border: 1px solid {c['border']}; }}
    QSplitter::handle {{ background: {c['border']}; }}
    QMenu {{ background: {c['raised']}; border: 1px solid {c['border']}; padding: 4px; }}
    QMenu::item {{ padding: 6px 24px; }}
    QScrollBar:vertical {{ background: {c['app']}; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; min-height: 24px; border-radius: 4px; }}
    """
