"""Reproducible, project-local authoring guides for the native game templates."""
import json
from pathlib import Path
import shutil
from .registry import ROOT, Registry
from .functions import scoped_registry
from .document import write_text_if_changed
from .node_help import description, md_value, port_table


FUNCTION_STEPS = {
    'Refresh HUD': 'Đọc score/best → Format Integer → Concat Strings → Set Widget Text. Chọn thông báo theo alive/started/paused, rồi dùng display=none khi chuỗi rỗng.',
    'Game Over': 'Đặt alive=false và velocity=0; lưu Reason, lấy max(best, score), cập nhật HUD rồi Return.',
    'Reset Round': 'Đặt seed 42017, xóa score/steps/velocity, phục hồi alive và vị trí chim. Đặt lại ba cặp cột tại X=4,8,12, xóa cờ passed và cập nhật HUD; giữ best.',
    'Flap': 'Branch chỉ cho qua khi alive AND NOT paused. Đặt started=true và velocity=5.5, chọn sprite state flap rồi cập nhật HUD.',
    'Advance Pipe 1': 'Dịch cột bằng 2.6 × delta time. Nếu X < -8, cộng 12 vào X, lấy gap ngẫu nhiên và reset passed. Sequence First tính điểm một lần, Then cập nhật vị trí hai cột và kiểm tra va chạm.',
    'Advance Pipe 2': 'Dùng cùng quy tắc Advance Pipe 1 cho nhóm pipe_1; giữ nguyên dây nối nhưng đổi tên biến/entity đúng nhóm.',
    'Advance Pipe 3': 'Dùng cùng quy tắc Advance Pipe 1 cho nhóm pipe_2; mỗi nhóm có gap và cờ passed riêng.',
    'Simulate Bird': 'Tăng steps; tính velocity = velocity - 15 × dt, bird_y = bird_y + velocity × dt. Gán vị trí chim, tiến ba nhóm cột, kiểm tra sàn/trần rồi gọi Game Over nếu vượt biên.',
    'Refresh board': 'For Each Entity duyệt pool body_entities. Bật entity khi Index < length(snake); trong nhánh True lấy snake[Index] và gán vị trí. Done dời food, ghi score/best/status vào HUD.',
    'Spawn food': 'Random Integer chọn một ô bắt đầu. Duyệt tối đa 144 ô với phép modulo; quy đổi chỉ số sang X/Z. Bỏ ô đã có thân, chọn ô trống đầu tiên và Break. Không có ô trống thì End round với thông báo thắng.',
    'End round': 'Đặt alive=false; ghi Reason vào status và death_reason; cập nhật bảng và Return.',
    'Reset round': 'Khôi phục bốn ô thân ban đầu, hướng +X, food=[6,0.5,5], score/steps=0, alive=true. Xóa pause/turn lock/lý do chết, reset seed, Start Timer snake-tick 0.18 giây lặp và Refresh board; giữ best.',
    'Advance snake': 'Chỉ chạy khi alive AND NOT paused. Tính đầu mới, kiểm tra biên bàn. Nếu không ăn thì bỏ đuôi trước khi kiểm tra tự cắn; nếu ăn thì giữ đuôi. Chèn đầu mới, tăng score/best nếu ăn, Spawn food và Refresh board.',
    'Request turn': 'Cho đổi hướng khi còn sống, không pause, chưa đổi hướng trong tick. Dot Product > -0.5 chặn quay ngược; đặt direction, khóa lượt quay và xoay đầu theo Yaw.',
}


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]])


def guide_markdown(root, kind):
    root = Path(root)
    graph = json.loads((root/'graphs/gameplay.json').read_text('utf-8'))
    scene = json.loads((root/'scenes/main.json').read_text('utf-8'))
    functions = graph['functions']
    base = Registry()
    is_flappy = kind == 'flappy'
    title = 'Flappy Bird' if is_flappy else 'Isometric Snake 3D'
    project_name = 'flappy_bird' if is_flappy else 'isometric_snake_3d'
    variables = {name: value if isinstance(value, dict) and 'type' in value else dict(type='float', value=value)
                 for name, value in scene['variables'].items()}
    controls = 'Space hoặc chuột trái: bắt đầu/vỗ cánh; P: pause/resume; R: reset vòng.' if is_flappy else 'WASD/phím mũi tên: rẽ; P: pause/resume; R: reset vòng. Game chạy ngay khi Play.'
    text = [f'# {title} — Hướng dẫn dựng game bằng node',
            'Tài liệu lấy từ graph và scene đã lưu, gồm từng node, hằng số và mọi dây nối. Có thể đọc/sửa file này bằng **File > Project Markdown…** trong Node_Engine (Ctrl+Shift+M).',
            f'![Ảnh gameplay native đã kiểm chứng](images/game.png)',
            '## 1. Mở và thử template',
            f'1. Mở Project Manager > Open, chọn `{project_name}.nen` trong thư mục template.\n'
            '2. Nhấn F5 và click vùng game để bàn phím vào đúng cửa sổ native.\n'
            f'3. {controls}\n'
            '4. Nhấn F6 để pause host, Shift+F5 để dừng. Phím P của game chỉ dừng gameplay của template, khác nút Pause của host.\n'
            '5. Best score giữ qua reset vòng trong cùng phiên chạy; chưa có lưu kỷ lục qua lần mở game mới.',
            '## 2. Chuẩn bị một project mới',
            '1. File > New Project…; chọn Blank 2D cho Flappy hoặc Blank 3D cho Snake, đặt tên/thư mục riêng.\n'
            '2. Dùng template gốc làm mẫu đối chiếu. Copy các file assets của template vào assets của project mới.\n'
            '3. Tạo entity/camera và tài nguyên theo bảng dưới. Chọn entity, copy Stable ID trong Inspector; dùng ID mới đó thay cho ID nguồn ở mọi input Entity và mảng body_entities. Tên hiển thị không thay thế Stable ID.\n'
            '4. Scene > Scene Variables…: khai báo đúng tên, kiểu và giá trị ban đầu.\n'
            '5. Scene > UI Templates…: tạo asset hud, dán RML bên dưới; id phần tử phải khớp Set Widget Text.\n'
            '6. Graph > New Function…: tạo TẤT CẢ signature trong bảng function trước, sau đó Graph > Edit Function… để dựng body. Function action giữ ô Pure bỏ chọn.\n'
            '7. Trong từng body, thêm node theo bảng chi tiết, điền hằng số rồi nối chính xác source.port → target.port. Function Input/Output có sẵn theo signature.\n'
            '8. Dựng Gameplay sau các function. Graph > Validate; Ctrl+S; F5 và thử lại các tình huống ở cuối tài liệu.',
            'Các nhãn node trong tài liệu như n1 là ID trong graph nguồn, dùng để phân biệt những node cùng tên. Khi dựng bằng UI, ID được cấp mới; có thể đặt nhãn tương ứng để theo dõi dây. Ảnh dây nối dùng renderer thật của editor, bố trí lại một trích đoạn để đọc rõ.',
            '## 3. Scene, assets và camera',
            f'Camera đang dùng: `{scene.get("active_camera", "")}`. Flappy hiển thị sprite trên XY, nhưng transform vẫn là vec3. Snake dùng mặt bàn XZ và camera orthographic.',
            table(['Entity ID', 'Position', 'Rotation', 'Scale', 'Tài nguyên / cấu hình'],
                  [(e['id'], md_value(e.get('position')), md_value(e.get('rotation')), md_value(e.get('scale')),
                    json.dumps({k:e[k] for k in ('mesh','sprite','material','camera','parent','active','sorting_layer','sorting_order') if k in e}, ensure_ascii=False)) for e in scene['entities']]),
            'Các giá trị transform là local; parent của mắt Snake là snake_head. 144 entity thân được tạo trước và Set Entity Active bật/tắt theo chiều dài thân. Có thể Duplicate Entity để tạo pool, rồi chọn đúng các entity trong biến body_entities.',
            '### Thư viện tài nguyên',
            'Scene > Sprites… / Materials… để khai báo những asset tương ứng. Cấu hình chính xác:',
            '```json\n' + json.dumps({k:scene[k] for k in ('sprite_assets','material_assets','features') if k in scene}, indent=2, ensure_ascii=False) + '\n```',
            '## 4. Biến scene',
            table(['Tên', 'Kiểu', 'Giá trị ban đầu'], [(name, value['type'], md_value(value['value'])) for name,value in variables.items()]),
            'Get/Set Variable kiểu float có tên ngắn; Integer/Boolean/String/Vector3/Array có node riêng. Biến pure Get đọc trạng thái tại lúc được dùng; Set chỉ ghi khi luồng exec đi qua.',
            '## 5. HUD',
            'Tạo UI Template với id `hud`; instance Widget cũng dùng tên `hud`. Nối Create Widget trước Reset Round/Reset round để không cập nhật một HUD chưa tồn tại.',
            '```html\n' + scene['ui_assets'][0]['rml'] + '\n```',
            '## 6. Tạo các function',
            table(['Function', 'ID nguồn', 'Loại', 'Tham số IN', 'Tham số OUT'],
                  [(f['name'], f['id'], 'Pure' if f['pure'] else 'Action', md_value(f['inputs']), md_value(f['outputs'])) for f in functions]),
            'Function ID nguồn chỉ phục vụ đối chiếu; UI tự cấp ID và tạo node gọi theo tên. Double-click node gọi hoặc Graph > Edit Function… để vào body. Save trong Function Graphs áp dụng thay đổi về project; Ctrl+S ở cửa sổ chính lưu xuống đĩa.',
            '## 7. Cách đọc từng bước node',
            'Mỗi mục dưới ghi tác dụng, IO và giá trị thực tế. Cổng có dây dùng giá trị từ dây; cổng không có dây dùng hằng số. Dây exec quyết định thứ tự thực thi, không phải vị trí node trên canvas. Các node pure được tính khi đầu ra cần dùng. Nhấn F1 trên node để tra cứu thêm.']
    bodies = [('Gameplay', None, graph)] + [(f['name'], f['id'], f['graph']) for f in functions]
    for label, fid, body in bodies:
        registry = scoped_registry(base, functions, fid)
        text.append(f'## {label} — {len(body["nodes"])} node')
        if label in FUNCTION_STEPS:
            text.append(FUNCTION_STEPS[label])
        elif is_flappy:
            text.append('On Game Start → Create Widget → Reset Round. Space/Mouse Down → Flap. R tăng restart_count rồi reset. P đảo paused và refresh HUD. On Update chỉ Simulate Bird khi started AND alive AND NOT paused.')
        else:
            text.append('On Game Start → Create Widget → Camera Look At → Reset round. On Timer Finished snake-tick → Advance snake. Phím hướng → Request turn(Direction,Yaw). R tăng restart_count rồi reset. P đổi paused/status rồi Refresh board.')
        for i, node in enumerate(body['nodes'], 1):
            spec = registry[node['type']]
            text += [f'### Bước {i}: {spec.name} · `{node["id"]}`', description(spec), port_table(spec)]
            incoming = {link['to'][1]: '.'.join(map(str,link['from'])) for link in body['links'] if link['to'][0] == node['id']}
            settings = []
            for port in spec.inputs:
                value = f'← {incoming[port.name]}' if port.name in incoming else 'không nối' if port.type == 'exec' else md_value(node.get('values',{}).get(port.name,port.default))
                settings.append((port.name, value))
            if settings:
                text += ['Cấu hình/nối đầu vào:', table(['IN', 'Giá trị hoặc source.port'], settings)]
            outgoing = [f'`{node["id"]}.{link["from"][1]} → {link["to"][0]}.{link["to"][1]}`' for link in body['links'] if link['from'][0] == node['id']]
            text.append('Nối đầu ra: ' + ('; '.join(outgoing) if outgoing else 'không có dây đi tiếp (kết thúc nhánh hoặc cổng chưa dùng).'))
        text += ['### Danh sách toàn bộ dây nối của ' + label,
                 table(['Từ node.cổng', 'Tới node.cổng'], [('.'.join(map(str,l['from'])), '.'.join(map(str,l['to']))) for l in body['links']])]
    text += ['## 8. Tình huống cần thử',
             'Đối chiếu acceptance.json và replays/*.json của project. Các frame replay dùng input xác định, không phải AI chơi thử.',
             table(['Kịch bản', 'Frame kết thúc', 'Ý nghĩa', 'Kết quả phải đạt'],
                   [(s['id'], s['frames'], ', '.join(s.get('covers',[])), '; '.join(f"{a['path']} {a['op']} {md_value(a['value'])}" for a in s['assertions']))
                    for s in json.loads((root/'acceptance.json').read_text('utf-8'))['scenarios']]),
             '## 9. Lỗi thường gặp',
             '- Không điều khiển được: click vùng game; Esc trả focus về editor.\n'
             '- Không thấy HUD: kiểm tra Create Widget chạy trước, Template/Widget=hud, id Element đúng RML.\n'
             '- Dây không nối được: kiểm tra kiểu int/float, vec2/vec3 và input cấu hình event là hằng số.\n'
             '- Không đọc được Item/Index/random Value: dùng trong nhánh Body/Out của node tạo payload.\n'
             '- Snake rẽ ngược/đổi hai lần: kiểm tra Dot Product và turn_locked; khóa được xóa mỗi tick.\n'
             '- Game không chạy: Graph > Validate, xem Problems/Console.\n'
             '- Chỉnh graph nhưng bản chạy đóng gói chưa đổi: Build lại, verify lại và package vào thư mục mới.\n'
             '- Ảnh Markdown không hiện: ảnh phải tồn tại bên trong project và đường dẫn tính từ thư mục file .md.',
             '## 10. Build và chia sẻ',
             'Build > Build Game biên dịch graph hiện tại; Build > Run Built Game chạy bản build. Các launcher Play.cmd/Replay.cmd của template dùng dist đã đóng gói. Khi thay đổi gameplay phải kiểm chứng rồi đóng gói lại theo tài liệu docs/template-games.md của engine.',
             'File .nen, graphs/, scenes/, assets/, acceptance.json, replays/ và docs/ là nguồn cần chia sẻ. generated/, build/, dist/, trạng thái save/test là đầu ra cục bộ có thể tạo lại.']
    return '\n\n'.join(text) + '\n'


def write_game_guide(root, kind):
    root = Path(root)
    from .project_markdown import PROJECT_GITIGNORE
    write_text_if_changed(root/'.gitignore', PROJECT_GITIGNORE)
    # Generators write source documents only; images come from verified native
    # captures in the engine docs, never from an invented gameplay screenshot.
    screenshot = ROOT / 'docs/images/games' / ('flappy.png' if kind == 'flappy' else 'snake.png')
    if screenshot.exists():
        target = root/'docs/images/game.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != screenshot.read_bytes():
            shutil.copy2(screenshot, target)
    write_text_if_changed(root/'docs/guide.md', guide_markdown(root, kind))
