"""Unreal-style project browser: categories, thumbnail grid, preview and creation defaults."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QRectF, QSettings, QStandardPaths, QUrl, QLockFile
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QFont, QLinearGradient, QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
    QListView, QStyledItemDelegate, QStyle, QComboBox, QStackedWidget, QMenu)
from editor import __version__
from editor.core.registry import ROOT
from editor.core.document import create_project, save_json, default_scene
from editor.core.projects import project_snapshot, project_child
from editor.core.project_format import PROJECT_FILTER
from editor.core.project_history import (read_history, merge_history, remember, discover_projects,
    describe_project, path_key, MAX_RECENT)


def history_path(settings):
    if settings.organizationName()=='NodeEngine' and settings.applicationName() in ('ObsidianStudio','Obsidian Studio'):
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation))/'NodeEngine/project-history.json'
    return Path(settings.fileName()).with_suffix('.projects.json')


def _paths(value):
    if isinstance(value,str):
        try:
            parsed=json.loads(value)
            if isinstance(parsed,list): return _paths(parsed)
        except ValueError:
            pass
        return [value] if value.strip() else []
    return [p for p in value if isinstance(p,str) and p.strip()] if isinstance(value,list) else []


def history_entries(settings):
    sources=[settings]
    if settings.organizationName()=='NodeEngine':
        sources += [QSettings('NodeEngine',name) for name in ('ObsidianStudio','Obsidian Studio')
                    if name!=settings.applicationName()]
    legacy=[]
    for source in sources:
        for key in ('projects/recent','recentProjects','recent_projects','lastProject','last_project'):
            legacy.extend(_paths(source.value(key,[])))
    return merge_history(history_path(settings),legacy)


def recent_projects(settings):
    return [entry['path'] for entry in history_entries(settings)]


def remember_project(settings,path):
    lock=None
    try:
        store=history_path(settings); store.parent.mkdir(parents=True,exist_ok=True)
        lock=QLockFile(str(store)+'.lock')
        if not lock.tryLock(250): return False
        entries=remember(store,path,recent_projects(settings))
        settings.setValue('projects/recent',[entry['path'] for entry in entries])
        settings.sync()
        return True
    except (OSError,ValueError):
        return False
    finally:
        if lock is not None: lock.unlock()


def project_art(name,kind='3d',size=QSize(640,320)):
    """Original Qt-drawn thumbnails; no Unreal artwork is shipped."""
    result=QPixmap(size); result.fill(QColor('#181b20'))
    painter=QPainter(result); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size.width()/640,size.height()/320)
    hue=hashlib.sha256(name.encode('utf-8',errors='replace')).digest()[0]
    accent=QColor.fromHsv(190+hue%45,110,195)
    gradient=QLinearGradient(0,0,640,320)
    gradient.setColorAt(0,QColor('#282d35')); gradient.setColorAt(1,QColor('#11151b'))
    painter.fillRect(QRectF(0,0,640,320),gradient)
    painter.setPen(QPen(QColor('#343b46'),1))
    for x in range(-400,1000,70): painter.drawLine(x,320,320+(x-320)//4,120)
    for y in (140,165,200,250,315): painter.drawLine(0,y,640,y)
    painter.setPen(QPen(accent.lighter(140),3)); painter.setBrush(accent.darker(155))
    if kind=='2d':
        for x,y in [(160,170),(230,135),(300,170),(370,135)]: painter.drawRoundedRect(QRectF(x,y,64,64),5,5)
        painter.setBrush(accent.lighter(140)); painter.drawEllipse(QRectF(294,66,45,45))
    elif kind=='folder':
        painter.drawRoundedRect(QRectF(195,99,248,150),10,10)
        painter.drawRoundedRect(QRectF(195,76,108,45),7,7)
        painter.setPen(QPen(accent.lighter(150),5))
        painter.drawLine(260,160,380,160); painter.drawLine(260,190,350,190)
    else:
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        def face(points,color):
            painter.setBrush(color); painter.drawPolygon(QPolygonF([QPointF(*p) for p in points]))
        face([(320,67),(405,113),(320,160),(235,113)],accent.lighter(125))
        face([(235,113),(320,160),(320,255),(235,207)],accent.darker(125))
        face([(320,160),(405,113),(405,207),(320,255)],accent.darker(175))
    painter.end()
    return result


def thumbnail(data):
    path=Path(data.get('path','.'))
    candidates=[path.parent/'ProjectThumbnail.png',path.parent/'.node_engine/thumbnail.png']
    if isinstance(data.get('thumbnail'),str) and data['thumbnail']:
        try: candidates.insert(0,project_child(path.parent,data['thumbnail']))
        except (OSError,ValueError): pass
    for candidate in candidates:
        if candidate.is_file():
            from PySide6.QtGui import QImageReader
            reader=QImageReader(str(candidate)); dimensions=reader.size()
            if dimensions.isValid() and dimensions.width()*dimensions.height()<=16_000_000:
                reader.setScaledSize(QSize(640,320)); picture=reader.read()
                if not picture.isNull(): return QPixmap.fromImage(picture)
    name=data.get('name','Project')
    kind='2d' if any(word in name.casefold() for word in ('2d','sprite','flappy','tile')) else '3d'
    return project_art(name,kind)


class ProjectCardDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        data=index.data(Qt.ItemDataRole.UserRole+1)
        if not data: return
        painter.save(); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=option.rect.adjusted(2,2,-2,-2)
        selected=bool(option.state&QStyle.StateFlag.State_Selected)
        painter.setPen(QPen(QColor('#1689e7') if selected else QColor('#393c42'),2 if selected else 1))
        painter.setBrush(QColor('#126db3') if selected else QColor('#303237'))
        painter.drawRoundedRect(rect,3,3)
        picture=data['image']
        image_rect=rect.adjusted(2,2,-2,-62)
        draw_cover(painter,image_rect,picture)
        painter.setPen(QColor('#ffffff')); font=QFont(option.font); font.setBold(True); painter.setFont(font)
        text=painter.fontMetrics().elidedText(data['name'],Qt.TextElideMode.ElideRight,rect.width()-16)
        painter.drawText(rect.adjusted(8,rect.height()-55,-8,-29),Qt.AlignmentFlag.AlignVCenter,text)
        painter.setFont(option.font); painter.setPen(QColor('#c3ceda') if selected else QColor('#a6abb3'))
        caption=data.get('caption',data.get('version',''))
        painter.drawText(rect.adjusted(8,rect.height()-29,-8,-7),Qt.AlignmentFlag.AlignVCenter,
                         option.fontMetrics.elidedText(caption,Qt.TextElideMode.ElideRight,rect.width()-16))
        painter.restore()


def draw_cover(painter,target,picture):
    source=QRectF(picture.rect()); center=source.center()
    ratio=target.width()/max(1,target.height())
    if source.width()/max(1,source.height())>ratio: source.setWidth(source.height()*ratio)
    else: source.setHeight(source.width()/ratio)
    source.moveCenter(center)
    painter.drawPixmap(QRectF(target),picture,source)


class PreviewLabel(QLabel):
    def paintEvent(self,event):
        picture=self.pixmap()
        if picture is None or picture.isNull(): return super().paintEvent(event)
        painter=QPainter(self); draw_cover(painter,self.rect(),picture)


BROWSER_STYLE='''
QDialog#ProjectLauncher, QDialog#NewProjectDialog { background:#202124; }
QWidget { color:#dedfe2; font-family:"Segoe UI"; font-size:12px; background:transparent; }
QFrame#sidebar { background:#17181b; border-right:1px solid #383a40; }
QFrame#details { background:#25262a; border-left:1px solid #383a40; }
QFrame#footer { background:#191a1d; border-top:1px solid #383a40; }
QLabel#brand { font-size:18px; font-weight:600; color:white; }
QLabel#heading { font-size:17px; font-weight:600; color:white; }
QLabel#section { font-size:11px; font-weight:600; color:#999fa9; }
QLabel#subtle { color:#9298a2; }
QLabel#status { color:#b9c0ca; }
QLabel#status[error="true"] { color:#ff8a81; }
QLineEdit,QComboBox { background:#131417; border:1px solid #42454b; border-radius:3px; padding:7px; }
QLineEdit:focus,QComboBox:focus { border:1px solid #1689e7; }
QPushButton { background:#35373c; border:1px solid #474a51; border-radius:3px; padding:7px 14px; }
QPushButton:hover { background:#44474d; }
QPushButton:focus { border:1px solid #279af3; }
QPushButton:disabled { color:#6f737d; background:#292b30; }
QPushButton#primary { background:#087bc7; border:1px solid #1599ec; color:white; font-weight:600; min-width:110px; }
QPushButton#primary:hover { background:#1694e3; }
QPushButton#primary:disabled { background:#30343a; border-color:#43464e; color:#818896; }
QPushButton#category { background:#272a30; border:1px solid #42454c; text-align:left; font-weight:600; padding:15px; }
QPushButton#category:checked { border:2px solid #1689e7; background:#183d5a; }
QListWidget { background:#202124; border:0; outline:0; }
QScrollBar:vertical { background:#202124; width:9px; }
QScrollBar::handle:vertical { background:#4b4e55; border-radius:4px; min-height:28px; }
QMenu { background:#2b2d32; border:1px solid #474a51; padding:4px; }
QMenu::item { padding:7px 20px; }
QMenu::item:selected { background:#126db3; }
'''


class ProjectLauncher(QDialog):
    def __init__(self,settings,parent=None,initial_project=None,error='',*,start_new=False,project_roots=None):
        super().__init__(parent)
        self.settings=settings; self.project_path=None; self.mode='recent'; self.catalog=[]
        self.project_roots=list(project_roots) if project_roots is not None else [ROOT/'projects',ROOT/'examples',ROOT/'templates/games']
        self.setObjectName('ProjectLauncher'); self.setWindowTitle('Node_Engine Project Browser')
        self.setStyleSheet(BROWSER_STYLE); self.setMinimumSize(920,540)
        self.resize(min(1180,QApplication.primaryScreen().availableGeometry().width()-40),
                    min(720,QApplication.primaryScreen().availableGeometry().height()-50))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)
        body=QHBoxLayout(); body.setSpacing(0); layout.addLayout(body,1)
        sidebar=QFrame(); sidebar.setObjectName('sidebar'); sidebar.setFixedWidth(195)
        side=QVBoxLayout(sidebar); side.setContentsMargins(14,22,14,18); side.setSpacing(12)
        brand=QLabel('N / NODE_ENGINE'); brand.setObjectName('brand'); side.addWidget(brand)
        version=QLabel('OBSIDIAN STUDIO  '+__version__); version.setObjectName('subtle'); side.addWidget(version)
        side.addSpacing(20)
        self.recent_button=self.category('RECENT PROJECTS','recent',side)
        self.new_button=self.category('GAMES\nNew project','new',side)
        self.examples_button=self.category('EXAMPLES\nExplore the engine','examples',side)
        side.addStretch()
        add_folder=QPushButton('Add project folder…'); add_folder.clicked.connect(self.add_folder); side.addWidget(add_folder)
        side.addWidget(QLabel('Node graphs · Native runtime'))
        body.addWidget(sidebar)
        center=QWidget(); main=QVBoxLayout(center); main.setContentsMargins(22,22,22,16); main.setSpacing(14)
        self.heading=QLabel(); self.heading.setObjectName('heading'); main.addWidget(self.heading)
        search_row=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('Search projects…')
        self.search.setAccessibleName('Search projects'); self.search.setClearButtonEnabled(True)
        search_row.addWidget(self.search,1); self.sort=QComboBox(); self.sort.addItems(['Recently opened','Name','Engine version'])
        self.sort.setAccessibleName('Sort projects'); search_row.addWidget(self.sort); main.addLayout(search_row)
        self.count_label=QLabel(); self.count_label.setObjectName('subtle'); main.addWidget(self.count_label)
        self.recent=QListWidget(); self.recent.setAccessibleName('Recent projects')
        self.recent.setViewMode(QListView.ViewMode.IconMode); self.recent.setResizeMode(QListView.ResizeMode.Adjust)
        self.recent.setMovement(QListView.Movement.Static); self.recent.setSpacing(10); self.recent.setGridSize(QSize(174,163))
        self.recent.setItemDelegate(ProjectCardDelegate(self.recent)); self.recent.setWordWrap(True)
        self.recent.currentItemChanged.connect(self.select_recent)
        self.recent.itemActivated.connect(lambda item:self.open_project() if self.mode!='new' else None)
        self.recent.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.recent.customContextMenuRequested.connect(self.context_menu)
        main.addWidget(self.recent,1)
        self.empty=QLabel('No projects found. Browse for a .nen file or add a project folder.')
        self.empty.setWordWrap(True); main.addWidget(self.empty); body.addWidget(center,1)
        details=QFrame(); details.setObjectName('details'); details.setFixedWidth(270)
        info=QVBoxLayout(details); info.setContentsMargins(17,22,17,20); info.setSpacing(12)
        self.preview=PreviewLabel(); self.preview.setFixedHeight(134); info.addWidget(self.preview)
        self.detail_name=QLabel('Select a project'); self.detail_name.setObjectName('heading'); self.detail_name.setWordWrap(True); info.addWidget(self.detail_name)
        self.description=QLabel('Choose a project to see its location and engine version.'); self.description.setWordWrap(True); info.addWidget(self.description)
        self.detail_fields=QLabel(); self.detail_fields.setWordWrap(True); self.detail_fields.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); info.addWidget(self.detail_fields)
        info.addStretch(); self.defaults_label=QLabel('PROJECT DEFAULTS'); self.defaults_label.setObjectName('section'); info.addWidget(self.defaults_label)
        self.defaults=QLabel('Implementation     Node Graph + C++\n\nTarget platform     Desktop\n\nRuntime                SDL3 / Vulkan')
        info.addWidget(self.defaults); body.addWidget(details)
        for label in (self.detail_name,self.description,self.detail_fields): label.setTextFormat(Qt.TextFormat.PlainText)
        self.details_layout=info; self.sidebar_layout=side
        footer=QFrame(); footer.setObjectName('footer'); bottom=QVBoxLayout(footer); bottom.setContentsMargins(20,12,20,14)
        self.fields=QStackedWidget(); bottom.addWidget(self.fields)
        open_page=QWidget(); open_row=QHBoxLayout(open_page); open_row.setContentsMargins(0,0,0,0)
        open_row.addWidget(QLabel('Project file'))
        self.path=QLineEdit(str(initial_project) if initial_project else ''); self.path.setAccessibleName('Project file')
        self.path.setPlaceholderText('Select a project or browse for a .nen / project.json file'); open_row.addWidget(self.path,1)
        self.browse_button=QPushButton('Browse…'); self.browse_button.clicked.connect(self.browse); open_row.addWidget(self.browse_button)
        self.fields.addWidget(open_page)
        new_page=QWidget(); new_row=QHBoxLayout(new_page); new_row.setContentsMargins(0,0,0,0)
        new_row.addWidget(QLabel('Project folder')); self.directory=QLineEdit(str(ROOT/'projects/MyGame'))
        self.directory.setAccessibleName('New project folder'); new_row.addWidget(self.directory,1)
        folder=QPushButton('…'); folder.setAccessibleName('Browse project parent folder'); folder.clicked.connect(self.browse_parent); new_row.addWidget(folder)
        new_row.addWidget(QLabel('Project name')); self.name=QLineEdit('MyGame'); self.name.setMinimumWidth(180); self.name.setMaximumWidth(240)
        self.name.setAccessibleName('Project name'); new_row.addWidget(self.name); self.fields.addWidget(new_page)
        row=QHBoxLayout(); self.message=QLabel(error); self.message.setObjectName('status'); self.message.setAccessibleName('Project open status'); self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        row.addWidget(self.message,1)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.open_button=self.buttons.button(QDialogButtonBox.StandardButton.Ok); self.open_button.setObjectName('primary')
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Cancel' if parent else 'Exit')
        self.buttons.accepted.connect(self.open_project); self.buttons.rejected.connect(self.reject); row.addWidget(self.buttons)
        bottom.addLayout(row); layout.addWidget(footer)
        self.search.textChanged.connect(self.populate); self.sort.currentIndexChanged.connect(self.populate)
        self.path.returnPressed.connect(self.open_project); self.path.textChanged.connect(self.path_changed)
        self.reload_catalog(); self.change_mode('new' if start_new else 'recent',keep_path=True)
        if initial_project: self.path.setText(str(initial_project)); self.path_changed()
        if error: self.show_error(error)

    def category(self,title,mode,layout):
        button=QPushButton(title); button.setObjectName('category'); button.setCheckable(True)
        button.setMinimumHeight(53); button.setMaximumHeight(87)
        button.clicked.connect(lambda:self.change_mode(mode)); layout.addWidget(button,1)
        return button

    def reload_catalog(self):
        self.catalog=[dict(describe_project(entry['path'],entry.get('opened_at',''),'recent'),rank=index)
                      for index,entry in enumerate(history_entries(self.settings))]
        seen={path_key(data['path']) for data in self.catalog}
        roots=self.project_roots+_paths(self.settings.value('projects/search_roots',[]))
        for path in discover_projects(roots):
            if path_key(path) not in seen:
                self.catalog.append(describe_project(path,source='existing')); seen.add(path_key(path))

    def change_mode(self,mode,keep_path=False):
        self.mode=mode
        for button,key in [(self.recent_button,'recent'),(self.new_button,'new'),(self.examples_button,'examples')]: button.setChecked(key==mode)
        self.heading.setText({'recent':'RECENT PROJECTS','new':'GAMES','examples':'EXAMPLE PROJECTS'}[mode])
        self.fields.setCurrentIndex(1 if mode=='new' else 0)
        self.defaults.setVisible(mode=='new'); self.defaults_label.setVisible(mode=='new')
        self.open_button.setEnabled(mode=='new' or bool(self.path.text().strip()))
        self.open_button.setText('Create Project' if mode=='new' else 'Open Project')
        self.search.setPlaceholderText('Search templates…' if mode=='new' else 'Search projects…')
        self.sort.setVisible(mode!='new'); self.message.clear(); self.search.clear(); self.populate(keep_path=keep_path)

    def populate(self,*args,keep_path=False):
        selected=self.path.text() if hasattr(self,'path') else ''
        if self.mode=='new':
            entries=[dict(name='Blank 3D',path='template:3d',kind='3d',caption='3D node suggestions',version=__version__,source='template',description='Start with 3D and shared node suggestions. Sprites and tilemaps can also be added; choose All compatible nodes in the Node Library to combine workflows.'),
                     dict(name='Blank 2D',path='template:2d',kind='2d',caption='Orthographic camera',version=__version__,source='template',description='Start with an orthographic camera and 2D + shared node suggestions. Models can also be added; choose All compatible nodes in the Node Library to combine workflows.')]
        else:
            entries=list(self.catalog)
            if self.mode=='examples': entries=[data for data in entries if Path(data['path']).is_relative_to(ROOT/'examples') or Path(data['path']).is_relative_to(ROOT/'templates')]
            entries.sort(key=lambda data:data['name'].casefold())
            if self.sort.currentIndex()==0: entries.sort(key=lambda data:(data['source']!='recent',data.get('rank',MAX_RECENT)))
            elif self.sort.currentIndex()==2:
                def version(data):
                    try: return tuple(map(int,data['version'].split('.')))
                    except ValueError: return (-1,)
                entries.sort(key=version,reverse=True)
        query=self.search.text().casefold(); entries=[data for data in entries if query in (data['name']+' '+data['path']).casefold()]
        self.recent.blockSignals(True); self.recent.clear()
        for data in entries:
            data=dict(data)
            if data['source']!='template':
                data['caption']=('Not found' if not data['exists'] else 'Opened '+data['opened_at'][:10] if data['opened_at'] else 'Previously opened' if data['source']=='recent' else 'Existing project')+' · '+data['version']
            data['image']=project_art(data['name'],data.get('kind','3d')) if data['source']=='template' else thumbnail(data)
            data['image']=data['image'].scaled(320,160,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            item=QListWidgetItem(data['name']); item.setSizeHint(QSize(174,163))
            item.setData(Qt.ItemDataRole.UserRole,data['path']); item.setData(Qt.ItemDataRole.UserRole+1,data)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole,data.get('caption','')+' '+data['path'])
            item.setToolTip(data['name']+'\n'+data['path']+'\n'+data.get('caption','')); self.recent.addItem(item)
        self.recent.blockSignals(False); self.empty.setVisible(not entries)
        if self.mode=='new': self.open_button.setEnabled(bool(entries))
        self.count_label.setText(f'{len(entries)} templates' if self.mode=='new' else f'{len(entries)} projects  ·  History and existing projects on this computer')
        row=next((i for i,data in enumerate(entries) if data['path']==selected),0)
        if entries and not (keep_path and selected and all(data['path']!=selected for data in entries)): self.recent.setCurrentRow(row)
        elif not entries:
            if self.mode!='new' and not keep_path: self.path.clear()
            self.detail_name.setText('No matching projects'); self.description.setText('Browse for a project or choose another category.')
            self.detail_fields.clear(); self.preview.setPixmap(project_art('Projects','folder'))

    def select_recent(self,item,previous=None):
        if not item: return
        data=item.data(Qt.ItemDataRole.UserRole+1)
        self.preview.setPixmap(data['image']); self.detail_name.setText(data['name'])
        if self.mode=='new':
            self.template_kind=data['kind']; self.description.setText(data['description'])
            self.detail_fields.setText('Clean starter project\n\n.nen manifest + scenes / graphs / assets')
        else:
            self.path.setText(data['path']); self.show_project(data)

    def show_project(self,data):
        self.detail_name.setText(data['name']); self.preview.setPixmap(data.get('image') or thumbnail(data))
        self.description.setText(data['error'] or 'Open this project to continue working in the editor.')
        when='Previously opened' if data['source']=='recent' else 'Discovered on this computer'
        if data['opened_at']:
            try: when=datetime.fromisoformat(data['opened_at']).astimezone().strftime('%d %b %Y · %H:%M')
            except ValueError: pass
        self.detail_fields.setText(f"ENGINE VERSION\n{data['version']}  ·  {data['scene_count']} scene(s)\n\nLAST OPENED\n{when}\n\nLOCATION\n{Path(data['path']).parent}")

    def path_changed(self,*args):
        if self.mode=='new': return
        text=self.path.text().strip()
        self.open_button.setEnabled(bool(text))
        if text:
            try: data=next((entry for entry in self.catalog if path_key(entry['path'])==path_key(text)),None) or describe_project(text)
            except (OSError,ValueError): return
            self.show_project(data)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'preview'): return
        compact=self.height()<650
        self.preview.setFixedHeight(96 if compact else 134)
        self.details_layout.setSpacing(6 if compact else 12)
        self.sidebar_layout.setSpacing(6 if compact else 12)
        for button in (self.recent_button,self.new_button,self.examples_button): button.setMaximumHeight(70 if compact else 87)

    def show_error(self,text):
        self.message.setProperty('error',True); self.message.setText(text)
        self.message.style().unpolish(self.message); self.message.style().polish(self.message)

    def browse(self):
        path,_=QFileDialog.getOpenFileName(self,'Open Node_Engine Project',self.path.text() or str(ROOT),PROJECT_FILTER)
        if path: self.path.setText(path)

    def browse_parent(self):
        parent=QFileDialog.getExistingDirectory(self,'Project parent directory',str(Path(self.directory.text()).parent))
        if parent: self.directory.setText(str(Path(parent)/(self.name.text().strip() or 'MyGame')))

    def add_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Find existing Node_Engine projects',str(ROOT))
        if folder:
            roots=_paths(self.settings.value('projects/search_roots',[]))
            if folder not in roots: roots.append(folder)
            self.settings.setValue('projects/search_roots',roots); self.settings.sync()
            self.reload_catalog(); self.change_mode('recent')

    def context_menu(self,position):
        item=self.recent.itemAt(position)
        if not item or self.mode=='new': return
        self.recent.setCurrentItem(item)
        menu=QMenu(self); action=menu.addAction('Show in Folder')
        if menu.exec(self.recent.viewport().mapToGlobal(position))==action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(item.data(Qt.ItemDataRole.UserRole)).parent)))

    def open_project(self):
        if self.mode=='new': return self.create()
        try:
            if not self.path.text().strip(): raise ValueError('Choose a .nen file or legacy project.json')
            path=Path(self.path.text().strip()).expanduser().resolve(); project_snapshot(path)
        except (OSError,ValueError,KeyError,TypeError) as error:
            self.show_error(f'Cannot open project: {error}'); return
        self.project_path=path; self.accept()

    def new_project(self):
        self.open_button.setEnabled(True); self.change_mode('new')

    def create(self):
        try:
            if not self.directory.text().strip(): raise ValueError('Choose a new project folder')
            path=create_project(self.directory.text(),self.name.text())
            from editor.core.project_format import load_manifest
            manifest=load_manifest(path)
            manifest['editor']={'node_workflow':getattr(self,'template_kind','3d')}
            save_json(path,manifest)
            if getattr(self,'template_kind','3d')=='2d':
                from editor.core.camera import default_camera
                scene=default_scene(); camera=default_camera(); camera['projection']='orthographic'
                scene['entities'].append(dict(id='camera',name='Camera',position=[0,0,10],rotation=[0,0,0],scale=[1,1,1],camera=camera))
                scene['active_camera']='camera'; save_json(path.parent/'scenes/main.json',scene)
            project_snapshot(path)
        except (OSError,ValueError) as error:
            self.show_error(str(error)); return
        self.project_path=path; self.accept()


class NewProjectDialog(ProjectLauncher):
    def __init__(self,parent=None):
        settings=getattr(parent,'settings',None) or QSettings('NodeEngine','ObsidianStudio')
        super().__init__(settings,parent,start_new=True)
        self.setObjectName('NewProjectDialog'); self.setWindowTitle('Node_Engine — New Project')
