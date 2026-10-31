"""Build offline guides and real editor graph excerpts from the saved templates."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from editor.core.registry import Registry
from editor.core.functions import scoped_registry
from editor.core.document import write_text_if_changed, save_json
from editor.core.game_guides import write_game_guide
from editor.core.node_help import node_markdown, examples
from editor.ui.node_help import render_nodes


def generate(verification):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    registry = Registry()
    images = ROOT/'docs/images/node-examples'
    images.mkdir(parents=True, exist_ok=True)
    candidates = {}
    for key, folder, scenario, page in [('flappy','flappy_bird','score','flappy-bird'),
                                         ('snake','isometric_snake_3d','eat','isometric-snake')]:
        project = ROOT/'templates/games'/folder
        evidence = Path(verification)/key
        report = json.loads((evidence/'checks.json').read_text('utf-8'))
        if not report['passed']:
            raise ValueError('Native verification must pass before generating gameplay screenshots: ' + key)
        screenshot = QImage(str(evidence/(scenario+'-node_game_view.bmp')))
        if screenshot.isNull():
            raise ValueError('Missing verified native capture: ' + key)
        target = ROOT/'docs/images/games'/(key+'.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        assert screenshot.scaledToWidth(760, Qt.TransformationMode.SmoothTransformation).save(str(target))
        graph = json.loads((project/'graphs/gameplay.json').read_text('utf-8'))
        for name, fid, body in [('Gameplay',None,graph)]+[(f['name'],f['id'],f['graph']) for f in graph['functions']]:
            scoped = scoped_registry(registry, graph['functions'], fid)
            for node in body['nodes']:
                if node['type'] not in registry.nodes:
                    continue
                adjacent = [link for link in body['links'] if node['id'] in (link['from'][0],link['to'][0])]
                rank = min(4, len(adjacent))
                if node['type'] not in candidates or rank > candidates[node['type']][0]:
                    candidates[node['type']] = (rank, key, folder, name, scoped, body, node)
    index = {}
    for tid, (_rank, key, folder, function, scoped, body, selected) in sorted(candidates.items()):
        incoming = [l['from'][0] for l in body['links'] if l['to'][0] == selected['id'] and l['from'][0] != selected['id']]
        outgoing = [l['to'][0] for l in body['links'] if l['from'][0] == selected['id'] and l['to'][0] != selected['id']]
        before = list(dict.fromkeys(incoming))[:2]
        after = [nid for nid in dict.fromkeys(outgoing) if nid not in before][:2]
        chosen = [*before,selected['id'],*after]
        nodes = []
        for node in body['nodes']:
            if node['id'] not in chosen:
                continue
            node = deepcopy(node)
            column = 0 if node['id'] in before else 2 if node['id'] in after else 1
            row = before.index(node['id']) if column == 0 else after.index(node['id']) if column == 2 else 0
            node['position'] = [column*290,row*190]
            nodes.append(node)
        links = [l for l in body['links'] if l['from'][0] in chosen and l['to'][0] in chosen]
        image = render_nodes(scoped,nodes,links,width=760)
        assert image.save(str(images/(str(tid)+'.png')))
        index[str(tid)] = dict(guide=key,graph=f'templates/games/{folder}/graphs/gameplay.json',function=function,node=selected['id'],
            caption=f'Trích đoạn {function} của {folder}: node {selected["id"]}. Đây là các node và dây nối thật từ graph đã chạy; vị trí được sắp lại để dễ đọc.')
        app.processEvents()
    save_json(images/'index.json',index)
    examples.cache_clear()
    text = ['# Tham chiếu toàn bộ node',
            f'{len(registry.nodes)} loại node builtin lấy từ nodes/registry.yaml. IO mặc định là của registry; function, event, struct/component của project có signature riêng được Help đọc trực tiếp khi mở project.',
            'Tra cứu trong editor: Help > Node Help… hoặc chọn node và F1. Ảnh node đơn được render theo signature hiện tại; các ví dụ có dây nối là trích đoạn từ hai game native đã kiểm chứng. Chỉ các game template có ảnh gameplay được kiểm chứng trong lần bàn giao này.']
    for category, label in registry.categories.items():
        text.append(f'## {category:02d}. {label}')
        for spec in sorted((n for n in registry.nodes.values() if n.category==category),key=lambda n:n.id):
            content = node_markdown(spec).replace('\n#', '\n##')
            content = content.replace('# '+spec.name, '### '+spec.name, 1)
            content = content.replace('(doc:', '(').replace('(guide:flappy)', '(games/flappy-bird.md)').replace('(guide:snake)', '(games/isometric-snake.md)')
            text += [f'<a id="node-{spec.id}"></a>',content]
    write_text_if_changed(ROOT/'docs/node-reference.md','\n\n'.join(text)+'\n')
    for key, folder, page in [('flappy','flappy_bird','flappy-bird'),('snake','isometric_snake_3d','isometric-snake')]:
        project = ROOT/'templates/games'/folder
        write_game_guide(project,key)
        content = (project/'docs/guide.md').read_text('utf-8').replace('(images/game.png)',f'(../images/games/{key}.png)')
        write_text_if_changed(ROOT/'docs/games'/(page+'.md'),content)
    print(f'Generated 2 complete game guides, {len(registry.nodes)} node entries, {len(index)} native graph example images.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verification',type=Path,default=ROOT/'artifacts/validation/template-help')
    generate(parser.parse_args().verification)
