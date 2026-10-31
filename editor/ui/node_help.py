"""Searchable offline help; images use the editor's real NodeGraphQt renderer."""
from copy import copy
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QUrl
from PySide6.QtGui import QColor, QImage, QPainter, QTextDocument, QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QSplitter,
    QWidget, QTreeWidget, QTreeWidgetItem, QLabel, QPushButton,
)
from NodeGraphQt import NodeGraph
from editor.core.registry import ROOT
from editor.core.node_help import GUIDES, node_markdown, description
from .graph import node_class, class_name
from .theme import stylesheet
from .project_markdown import LocalMarkdownBrowser


def render_nodes(registry, nodes, links=(), *, width=760):
    """Render native nodes without changing an authored graph or its undo stack."""
    small = copy(registry)
    small.nodes = {node['type']: registry[node['type']] for node in nodes}
    graph = NodeGraph()
    graph.set_acyclic(False)
    for spec in small.nodes.values():
        graph.register_node(node_class(spec, small))
    mapping = {}
    for data in nodes:
        spec = small[data['type']]
        item = graph.create_node(f'obsidian.{class_name(spec)}', name=data.get('label'),
                                 pos=data.get('position', [0, 0]), selected=False, push_undo=False)
        for key, value in data.get('values', {}).items():
            if key in {p.name for p in spec.data_inputs}:
                item.set_property('value_' + key, value, push_undo=False)
        if spec.kind == 'switch' and 'cases' in data:
            from .switches import configure_node
            configure_node(item, data['cases'], small)
        mapping[data['id']] = item
    for link in links:
        source, output = link['from']; target, input_name = link['to']
        mapping[source].outputs()[output].connect_to(mapping[target].inputs()[input_name], push_undo=False)
    scene = graph.viewer().scene()
    bounds = QRectF()
    for node in mapping.values():
        bounds = bounds.united(node.view.sceneBoundingRect())
    bounds = bounds.adjusted(-24, -24, 24, 24)
    scale = min(1.6, width / max(1, bounds.width()))
    image = QImage(max(1, round(bounds.width() * scale)), max(1, round(bounds.height() * scale)), QImage.Format.Format_ARGB32)
    image.fill(QColor('#0b0f15'))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, QRectF(image.rect()), bounds)
    painter.end()
    graph.widget.close()
    graph.widget.deleteLater()
    graph.deleteLater()
    return image


class NodeHelpDialog(QDialog):
    def __init__(self, registry, parent=None, *, spec=None, guide=None, cases=None):
        super().__init__(parent)
        self.setWindowTitle('Node_Engine Help — Hướng dẫn node & game')
        self.setObjectName('NodeHelpDialog')
        self.setStyleSheet(stylesheet())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
        self.resize(1200, 840)
        self.registry = copy(registry)
        self.registry.nodes = dict(registry.nodes)
        self.current_spec = None
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        title = QLabel('HELP  /  NODE ENGINE')
        title.setStyleSheet('font-size:18px;font-weight:600;padding:8px;color:#5dd6e8')
        bar.addWidget(title, 1)
        close = QPushButton('Đóng / Close')
        close.clicked.connect(self.close)
        bar.addWidget(close)
        layout.addLayout(bar)
        split = QSplitter()
        navigation = QWidget()
        nav = QVBoxLayout(navigation)
        nav.setContentsMargins(0, 0, 8, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Tìm tên, ID, kiểu cổng…')
        self.search.setAccessibleName('Search node help')
        self.category = QComboBox()
        self.category.setAccessibleName('Help category')
        self.category.addItem('Tất cả nhóm / All categories', None)
        for key, label in registry.categories.items():
            self.category.addItem(label, key)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAccessibleName('Help topics and nodes')
        self.empty = QLabel('Không tìm thấy node. Thử tên hoặc ID khác.')
        self.empty.setWordWrap(True)
        nav.addWidget(self.search)
        nav.addWidget(self.category)
        nav.addWidget(self.empty)
        nav.addWidget(self.tree, 1)
        split.addWidget(navigation)
        self.browser = LocalMarkdownBrowser(ROOT/'docs')
        self.browser.setAccessibleName('Node help content')
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setStyleSheet('QTextBrowser {background:#10141b;color:#f0f3f9;border:0;padding:18px;font-size:14px;}')
        self.browser.document().setDefaultStyleSheet('h1 {color:#5dd6e8;} h2 {color:#a78bfa;margin-top:22px;} th,td {padding:6px;} a {color:#5dd6e8;}')
        split.addWidget(self.browser)
        split.setSizes([310, 850])
        layout.addWidget(split, 1)
        self.status = QLabel('F1: trợ giúp node đang chọn · Hướng dẫn hoạt động offline · IO lấy từ registry hiện tại')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.search.textChanged.connect(self.filter)
        self.category.currentIndexChanged.connect(self.filter)
        self.tree.currentItemChanged.connect(self.select_topic)
        self.browser.anchorClicked.connect(self.follow_link)
        self.filter()
        if spec is not None:
            self.show_node(spec, cases=cases)
        else:
            self.show_guide(guide or 'start')

    def filter(self, *_):
        query = self.search.text().casefold().split()
        category = self.category.currentData()
        self.tree.blockSignals(True)
        self.tree.clear()
        guides = QTreeWidgetItem(self.tree, ['HƯỚNG DẪN / GUIDES'])
        for key, (label, _) in GUIDES.items():
            item = QTreeWidgetItem(guides, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, ('guide', key))
        groups = {}
        count = 0
        for spec in sorted(self.registry.nodes.values(), key=lambda s: (s.category, s.name.casefold())):
            if self.search.text().strip().isdigit() and spec.id != int(self.search.text().strip()):
                continue
            haystack = f'{spec.id} {spec.name} {description(spec)} ' + ' '.join(p.type for p in (*spec.inputs, *spec.outputs))
            if category is not None and spec.category != category or not all(q in haystack.casefold() for q in query):
                continue
            if spec.category not in groups:
                groups[spec.category] = QTreeWidgetItem(self.tree, [self.registry.categories[spec.category]])
            item = QTreeWidgetItem(groups[spec.category], [f'{spec.name}  ·  {spec.id}'])
            item.setData(0, Qt.ItemDataRole.UserRole, ('node', spec.id))
            count += 1
        guides.setExpanded(True)
        for group in groups.values():
            group.setExpanded(bool(query) or category is not None)
        self.empty.setVisible(count == 0)
        self.tree.blockSignals(False)

    def select_topic(self, item, _previous):
        topic = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if topic:
            if topic[0] == 'guide':
                self.show_guide(topic[1])
            else:
                self.show_node(self.registry[topic[1]])

    def set_markdown(self, markdown, directory):
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(directory) + '/'))
        self.browser.setSearchPaths([str(directory)])
        self.browser.setMarkdown(markdown)
        self.browser.fit_images()
        self.browser.verticalScrollBar().setValue(0)

    def show_node(self, spec, *, cases=None):
        self.current_spec = spec
        preview_registry = copy(self.registry)
        preview_registry.nodes = {**self.registry.nodes, spec.id:spec}
        data = dict(id='preview', type=spec.id)
        if cases is not None:
            data['cases'] = cases
        image = render_nodes(preview_registry, [data], width=680)
        self.browser.document().setBaseUrl(QUrl.fromLocalFile(str(ROOT / 'docs') + '/'))
        self.set_markdown(node_markdown(spec, preview=True), ROOT / 'docs')
        self.browser.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl('help-preview:node'), image)
        self.browser.document().markContentsDirty(0, self.browser.document().characterCount())
        self.browser.fit_images()

    def show_guide(self, key):
        self.current_spec = None
        self.show_document(ROOT / 'docs' / GUIDES[key][1])

    def show_document(self, path):
        path = Path(path).resolve()
        docs = (ROOT / 'docs').resolve()
        if not path.is_relative_to(docs) or not path.is_file() or path.suffix != '.md':
            self.set_markdown('# Không mở được tài liệu\n\nChọn lại một hướng dẫn trong danh sách.', docs)
            return
        self.set_markdown(path.read_text('utf-8'), path.parent)

    def follow_link(self, url):
        if url.scheme() == 'node' and url.path().isdigit() and int(url.path()) in self.registry.nodes:
            self.show_node(self.registry[int(url.path())])
        elif url.scheme() == 'guide' and url.path() in GUIDES:
            self.show_guide(url.path())
        elif url.scheme() == 'doc':
            self.show_document(ROOT / 'docs' / url.path())
        elif url.scheme() in ('http', 'https'):
            QDesktopServices.openUrl(url)
        else:
            resolved = self.browser.document().baseUrl().resolved(url)
            if resolved.isLocalFile():
                if Path(resolved.toLocalFile()).suffix == '.md':
                    self.show_document(resolved.toLocalFile())
                    if url.fragment():
                        self.browser.scrollToAnchor(url.fragment())
                elif Path(resolved.toLocalFile()).suffix.lower() in ('.png', '.jpg') and Path(resolved.toLocalFile()).resolve().is_relative_to((ROOT / 'docs').resolve()):
                    QDesktopServices.openUrl(resolved)


def open_help(owner, adapter, node=None, *, guide=None):
    previous = getattr(owner, 'node_help_dialog', None)
    if previous is not None:
        previous.close()
    selected = node or next(iter(adapter.graph.selected_nodes()), None)
    spec = adapter.spec_for(selected) if selected is not None and guide is None else None
    cases = selected.get_property('switch_cases') if spec is not None and spec.kind == 'switch' else None
    dialog = NodeHelpDialog(adapter.registry, owner, spec=spec, guide=guide, cases=cases)
    owner.node_help_dialog = dialog
    dialog.destroyed.connect(lambda: setattr(owner, 'node_help_dialog', None) if getattr(owner, 'node_help_dialog', None) is dialog else None)
    dialog.show()
    return dialog
