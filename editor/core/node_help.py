"""Offline node reference, derived from the same signatures as the compiler."""
from functools import lru_cache
import json
import re
from .registry import ROOT


GUIDES = {
    'start': ('Bắt đầu / Getting started', 'node-help.md'),
    'flappy': ('Flappy Bird: từng bước', 'games/flappy-bird.md'),
    'snake': ('Isometric Snake: từng bước', 'games/isometric-snake.md'),
    'workspace': ('Dữ liệu & dọn workspace', 'workspace-hygiene.md'),
}

# Rules specific to the shipped game graphs; typed variants share these semantics.
NOTES = {
    'On Game Start': 'Chạy Out một lần khi bắt đầu phiên chơi. Tạo HUD trước khi gọi function cập nhật HUD.',
    'On Update': 'Chạy mỗi frame. Nhân tốc độ với Get Delta Time để chuyển từ đơn vị/giây sang độ dời của frame.',
    'On Timer Finished': 'Chạy khi timer có tên khớp Filter đến hạn. Snake dùng snake-tick lặp mỗi 0.18 giây.',
    'On Key Pressed': 'Chạy một lần khi phím Filter vừa được nhấn. Giữ phím không tự lặp sự kiện này.',
    'On Mouse Button': 'Phát sự kiện nút chuột khớp Filter. Kiểm tra Down bằng Branch để chỉ xử lý lúc nhấn.',
    'Branch': 'Nhận luồng In, kiểm tra Condition và chỉ chạy True hoặc False. Không nối cả hai nhánh như Sequence.',
    'Sequence': 'Chạy các đầu ra exec theo thứ tự khai báo. First hoàn tất rồi mới chạy Then.',
    'Break Loop': 'Thoát vòng lặp gần nhất và chuyển sang Done. Chỉ đặt trong Body của một vòng lặp.',
    'Continue Loop': 'Bỏ phần còn lại của lượt lặp hiện tại rồi sang lượt kế tiếp. Chỉ dùng trong Body.',
    'Function Input': 'Điểm vào function. Các tham số của function xuất hiện ở đầu ra; không thêm vào Gameplay.',
    'Function Output': 'Kết thúc function và trả kết quả về nơi gọi. Function action cần nối In trên các đường kết thúc.',
    'Start Timer': 'Tạo/thay timer Name với chu kỳ Seconds. Repeat=true lặp lại; Unscaled chọn đồng hồ không chịu time scale.',
    'Set Random Seed': 'Đặt lại luồng số ngẫu nhiên bằng Seed. Cùng seed và thứ tự gọi tạo cùng kết quả, hữu ích cho replay.',
    'Random Float': 'Khi In chạy, lấy một số thực trong khoảng Minimum..Maximum. Đọc Value trong luồng Out của lần gọi đó.',
    'Random Integer': 'Khi In chạy, lấy một số nguyên từ Minimum đến Maximum, gồm hai đầu. Đọc Value trong luồng Out.',
    'Get Delta Time': 'Trả số giây của bước game hiện tại sau time scale. Flappy dùng để tích phân vận tốc và vị trí.',
    'Set Position': 'Gán tọa độ local Value cho Entity. Không tự tạo va chạm; entity con chịu transform của cha.',
    'Set Rotation': 'Gán góc Euler local tính bằng độ cho Entity. Snake đổi hướng đầu bằng thành phần Y.',
    'Set Entity Active': 'Bật/tắt hoạt động Entity. Snake dùng để hiện đúng số đoạn thân trong pool 144 entity.',
    'Set Sprite State': 'Đổi state của sprite đã gán cho Entity; tên State phải tồn tại trong sprite asset.',
    'Camera Look At': 'Xoay camera nhìn về Target. Snake nhìn tâm bàn [5.5,0,5.5] từ camera orthographic.',
    'Create Widget': 'Tạo một instance Widget từ UI Template đã khai báo trong Scene > UI Templates. Tên instance phải duy nhất.',
    'Set Widget Text': 'Ghi Text vào phần tử Element của Widget đã tạo. Element là id trong RML; chuyển số thành chuỗi trước.',
    'Set Widget Style': 'Gán Property CSS của Element bằng chuỗi Value. Flappy đặt display=none/block cho bảng trạng thái.',
    'Format Integer': 'Chuyển int thành string để hiển thị số trên HUD; không thay đổi biến gốc.',
    'Concat Strings': 'Ghép chuỗi A rồi B. Flappy ghép SCORE với kết quả Format Integer.',
    'String Equal': 'Trả bool cho phép so sánh hai chuỗi A và B chính xác, phân biệt hoa thường.',
    'AND': 'Trả true khi A và B đều true. Dùng để gộp alive, started và NOT paused.',
    'OR': 'Trả true khi ít nhất một trong A, B là true. Flappy gộp va chạm sàn hoặc trần.',
    'NOT': 'Đảo bool Value: true thành false và ngược lại. Dùng để bật/tắt paused.',
    'Make Vector3': 'Ghép X, Y, Z thành vec3. Dùng để tạo vị trí trong cả game 2D và 3D.',
    'Vector Add': 'Cộng từng thành phần của hai vec3 A, B. Snake tính đầu mới = đầu cũ + direction.',
    'Dot Product': 'Trả tích vô hướng A·B. Với hai hướng đơn vị đối nhau, kết quả -1; Snake dùng để chặn quay ngược.',
    'Distance': 'Trả khoảng cách Euclid giữa hai điểm A và B. Snake coi khoảng cách tới food < 0.1 là ăn được.',
    'Point In Bounds': 'Trả bool cho biết Point nằm trong hộp Min..Max, gồm biên. Snake giới hạn X/Z từ 0 đến 11.',
    'Integer to Float': 'Chuyển số nguyên thành số thực. Cần khi nối chỉ số ô bàn vào thành phần vec3.',
    'Integer Divide': 'Chia số nguyên A cho B, bỏ phần thập phân. B không được bằng 0.',
    'Integer Modulo': 'Lấy phần dư của phép chia A cho B. B không được bằng 0; Snake dùng để quy đổi chỉ số ô.',
    'Add': 'Trả A + B dưới dạng float.', 'Integer Add': 'Trả A + B dưới dạng int; thường dùng tăng score hoặc bộ đếm.',
    'Subtract': 'Trả A - B dưới dạng float.', 'Integer Subtract': 'Trả A - B dưới dạng int.',
    'Multiply': 'Trả A × B; tốc độ × delta time cho độ dời trong một frame.',
    'Abs': 'Trả trị tuyệt đối của Value. Flappy dùng khoảng cách tuyệt đối tới tâm cột và khe.',
    'Less': 'Trả true khi A < B.', 'Integer Less': 'Trả true khi số nguyên A < B.',
    'Greater': 'Trả true khi A > B.', 'Integer Max': 'Trả số lớn hơn giữa A và B; dùng giữ best score.',
}

NOTES.update({
    'Divide': 'Trả A / B. B không được bằng 0.', 'Min': 'Trả giá trị nhỏ hơn trong A, B.',
    'Max': 'Trả giá trị lớn hơn trong A, B.', 'Lerp': 'Nội suy A + (B - A) × T; T=0 cho A, T=1 cho B. Không tự giới hạn T.',
    'Sin': 'Trả sin của góc đầu vào, tính bằng radian.', 'Cos': 'Trả cos của góc đầu vào, tính bằng radian.',
    'Tan': 'Trả tan của góc đầu vào, tính bằng radian.', 'Atan2': 'Trả góc atan2(Y,X) tính bằng radian.',
    'Modulo': 'Trả phần dư float theo fmod(A,B). B không được bằng 0.',
    'Power': 'Trả Base lũy thừa Exponent; kết quả phải là số hữu hạn.',
    'Sqrt': 'Trả căn bậc hai của Value; Value không được âm.',
    'Floor': 'Làm tròn xuống số nguyên gần nhất nhưng trả kiểu float.',
    'Ceil': 'Làm tròn lên số nguyên gần nhất nhưng trả kiểu float.',
    'Round': 'Làm tròn gần nhất; nửa đơn vị được làm tròn ra xa 0. Kết quả kiểu float.',
    'Inverse Lerp': 'Trả (Value-A)/(B-A). A và B phải khác nhau.',
    'SmoothStep': 'Nội suy mượt t²(3-2t), với t được tính bằng Inverse Lerp rồi giới hạn 0..1.',
    'Equal': 'So sánh A == B chính xác. Với float cần dung sai, dùng Nearly Equal.',
    'Not Equal': 'Trả true khi A khác B.', 'Less or Equal': 'Trả true khi A ≤ B.',
    'Greater or Equal': 'Trả true khi A ≥ B.', 'XOR': 'Trả true khi hai bool A và B khác nhau.',
    'Bitwise AND': 'Thực hiện phép AND trên từng bit của hai số nguyên.',
    'Bitwise OR': 'Thực hiện phép OR trên từng bit của hai số nguyên.',
    'Bitwise XOR': 'Thực hiện phép XOR trên từng bit của hai số nguyên.',
    'Integer Abs': 'Trả trị tuyệt đối của số nguyên Value.', 'Integer Min': 'Trả số nguyên nhỏ hơn trong A, B.',
    'Integer Multiply': 'Trả tích số nguyên A × B.', 'Integer Equal': 'Trả true khi hai số nguyên A và B bằng nhau.',
    'Integer Not Equal': 'Trả true khi hai số nguyên A và B khác nhau.',
    'Integer Less or Equal': 'So sánh hai số nguyên A ≤ B.', 'Integer Greater or Equal': 'So sánh hai số nguyên A ≥ B.',
    'Vector X': 'Tách thành phần X của vec3 Value.', 'Vector Y': 'Tách thành phần Y của vec3 Value.',
    'Vector Z': 'Tách thành phần Z của vec3 Value.',
    'Angle Between': 'Trả góc giữa A và B bằng radian. Cả hai vector phải có độ dài lớn hơn 0.',
    'Project Vector': 'Chiếu Value lên vector On; On có độ dài 0 cho vector 0.',
    'Reflect Vector': 'Phản xạ Value qua Normal. Normal phải khác vector 0 và được chuẩn hóa trước khi tính.',
    'Rotate Vector': 'Xoay vec3 bằng Euler Rotation tính theo độ.',
    'Vector Scale': 'Nhân từng thành phần Vector với Scale.', 'Magnitude': 'Trả độ dài Euclid của vec3.',
    'Normalize': 'Trả vec3 cùng hướng có độ dài 1; vector 0 cho kết quả 0.',
    'Cross Product': 'Trả tích có hướng A × B.', 'Vector Subtract': 'Trừ từng thành phần: A - B.',
    'Vector Lerp': 'Nội suy từng thành phần A + (B-A) × T.',
    'Make Quaternion': 'Tạo quaternion từ các thành phần theo cổng khai báo. Dùng Quaternion Normalize khi cần chuẩn hóa.',
    'Quaternion From Axis Angle': 'Tạo quaternion từ Axis và góc tính bằng độ.',
    'Quaternion Multiply': 'Kết hợp hai phép quay quaternion A và B theo thứ tự nhân.',
    'Quaternion Normalize': 'Chuẩn hóa quaternion; quaternion có độ dài 0 không hợp lệ.',
    'Quaternion Inverse': 'Trả phép quay đảo của quaternion được chuẩn hóa.',
    'Quaternion Slerp': 'Nội suy cầu giữa hai phép quay quaternion theo T.',
    'Quaternion Rotate Vector': 'Áp dụng phép quay quaternion lên vector.',
    'Identity Matrix': 'Tạo ma trận đơn vị 4×4.', 'Matrix Multiply': 'Nhân ma trận A × B theo thứ tự.',
    'Matrix Inverse': 'Tìm ma trận nghịch đảo; ma trận phải khả nghịch.',
    'Transform Point': 'Biến đổi điểm bằng ma trận, gồm cả thành phần tịnh tiến.',
    'Transform Direction': 'Biến đổi hướng bằng ma trận; hướng không có thành phần tịnh tiến.',
    'Make Transform Matrix': 'Ghép Position, Rotation quaternion và Scale thành ma trận transform.',
    'On Game Pause': 'Phát Out khi world được Pause World; biến paused của từng game không tự phát sự kiện này.',
    'On Game Resume': 'Phát Out khi world được Resume World.',
    'On Scene Load Failed': 'Nhận yêu cầu tải scene thất bại. Đọc payload lỗi trong luồng Out của sự kiện.',
    'Switch Integer': 'So sánh số nguyên Value với các case của instance; chạy case khớp, hoặc Default khi không khớp.',
    'Switch String': 'So sánh chuỗi Value với các case của instance; chạy case khớp, hoặc Default khi không khớp.',
    'C++ Code': 'Thực thi C++ nhúng của node trong runtime đã build hỗ trợ node code. Sửa bằng View/Edit Node Code, rồi Build Game.',
    'Set Replication Authority': 'Đặt quyền authority trong trạng thái replication cục bộ của world.',
    'Get Replication Authority': 'Đọc quyền authority của trạng thái replication cục bộ.',
    'Publish Replicated Value': 'Cập nhật giá trị replication cục bộ và revision theo quy tắc authority; node này không tự tạo kết nối mạng.',
    'Get Replicated Value': 'Đọc giá trị đã publish từ trạng thái replication cục bộ.',
    'Get Replication Revision': 'Đọc revision của trạng thái replication cục bộ để nhận biết thay đổi.',
    'Scene Load Succeeded': 'Đọc cờ thành công của thao tác tải scene. Kiểm tra cùng Get Scene Error để hiển thị lỗi.',
    'Closest Point On Segment': 'Trả điểm gần Point nhất trên đoạn thẳng từ A tới B.',
    'Closest Point On Bounds': 'Trả điểm gần Point nhất trên/trong hộp giới hạn Min..Max.',
    'Ray Plane Intersection': 'Tính điểm giao của ray với mặt phẳng từ các tham số hình học đầu vào.',
    'Ray Sphere Intersection Distance': 'Tính khoảng cách giao của ray với hình cầu. Đây là phép toán hình học, không truy vấn physics world.',
    'Line Segments Intersect 2D': 'Trả bool cho biết hai đoạn thẳng 2D có giao nhau.',
    'Bounds Min': 'Lấy tọa độ nhỏ nhất theo từng trục của mảng Points để tạo góc min của bounding box.',
    'Bounds Max': 'Lấy tọa độ lớn nhất theo từng trục của mảng Points để tạo góc max của bounding box.',
    'Ray Bounds Intersection Distance': 'Tính khoảng cách giao giữa ray và hộp giới hạn trục từ các tham số hình học.',
    'Random Vector': 'Sinh vec3 ngẫu nhiên theo các giới hạn đầu vào khi In chạy; đọc Value trong nhánh Out.',
    'Random Direction': 'Sinh hướng vec3 ngẫu nhiên có độ dài 1 khi In chạy; dùng Seed để replay lặp lại.',
    'Timer Exists': 'Kiểm tra timer Name có tồn tại trong phạm vi Owner hay không.',
    'Entity Reference': 'Tạo giá trị tham chiếu Entity từ ID cấu hình. Dùng Entity Exists để kiểm tra đối tượng còn tồn tại.',
    'Entity Exists': 'Trả bool cho biết tham chiếu Entity hiện trỏ tới một entity còn tồn tại.',
    'Find Entities By Name': 'Tìm và trả mảng entity có tên khớp Name trong scene.',
    'Add Entity Tag': 'Thêm Tag vào Entity để tìm hoặc lọc nhóm đối tượng.',
    'Find Entities By Tag': 'Trả mảng entity đang có Tag được yêu cầu.',
    'Find Entities By Layer': 'Trả mảng entity thuộc Layer được yêu cầu.',
    'Begin Profile Sample': 'Bắt đầu đo một mẫu profiler có tên. Ghép với End Profile Sample cùng tên.',
    'End Profile Sample': 'Kết thúc mẫu đo profiler đã bắt đầu để tích lũy thời gian.',
    'Clear Material': 'Gỡ material override được gán trên Entity để trở về material của mesh.',
    'Reset Material Parameters': 'Xóa các parameter override riêng của instance material trên Entity.',
    'Material Exists': 'Kiểm tra material asset có trong thư viện của scene.',
    'Clear Sprite': 'Gỡ sprite đang gán trên Entity.',
    'Sprite Exists': 'Kiểm tra sprite asset có trong thư viện của scene.',
    'Evaluate Cinematic Camera': 'Lấy vị trí vec3 của camera track tại Time. Nối kết quả vào Set Position của camera để áp dụng.',
    'Find Navigation Path': 'Tìm đường đi 2D từ Start tới Goal theo dữ liệu navigation của scene, trả mảng Path.',
    'Add Inventory Item': 'Thêm số lượng item yêu cầu vào inventory. Kiểm tra đầu ra để biết kết quả.',
    'Advance Quest': 'Tăng tiến độ quest theo đầu vào và quy tắc quest trong scene.',
    'Sound Exists': 'Kiểm tra sound asset có trong thư viện audio của scene.',
    'Widget Exists': 'Kiểm tra instance Widget đã được tạo và chưa bị hủy.',
    'Show Widget': 'Đặt trạng thái hiển thị của instance Widget.',
    'Focus Widget Element': 'Đưa focus bàn phím vào phần tử Element của Widget đã tạo.',
    'Open Save Storage': 'Mở vùng save riêng theo Game trước khi dùng slot/save/load. Save mặc định ở dữ liệu người dùng, không phải graph nguồn.',
    'Save Slot Exists': 'Kiểm tra Slot có tồn tại trong save storage đang mở.',
    'Save Variables': 'Lưu các biến có tên trong Names vào Slot. Trả bool kết quả; cần mở save storage trước.',
    'Load Variables': 'Đọc các biến Names từ Slot và phục hồi vào scene theo kiểu; kiểm tra Value/Get Save Error.',
    'Save JSON': 'Lưu chuỗi JSON hợp lệ dưới Key trong Slot; cần mở save storage trước.',
    'Load JSON': 'Đọc record Key của Slot và trả chuỗi JSON; kiểm tra trạng thái thao tác trước khi dùng.',
    'Save Operation Succeeded': 'Đọc cờ thành công của thao tác save storage gần nhất.',
    'Game Save Pending': 'Trả bool cho biết yêu cầu save/load toàn game đang chờ hoàn tất tại ranh giới frame.',
    'Wake Body': 'Đánh thức rigid body của Entity để tiếp tục mô phỏng.',
    'Sleep Body': 'Đưa rigid body của Entity vào trạng thái ngủ trong physics world.',
    'Physics Raycast Entity': 'Bắn ray vào physics world và trả entity trúng; dùng mask/lọc đầu vào phù hợp.',
    'Physics Overlap Sphere': 'Truy vấn các body chồng lấn vùng cầu trong physics world.',
    'Move Kinematic Body': 'Đặt mục tiêu chuyển động cho rigid body kinematic theo đầu vào của bước mô phỏng.',
    'Physics Sphere Cast': 'Quét hình cầu theo Displacement trong physics world; đọc Hit trước Entity/Point/Normal.',
    'Physics Box Cast': 'Quét hộp theo Displacement trong physics world; dùng Hit và Fraction để xử lý va chạm.',
    'Physics Capsule Cast': 'Quét capsule theo Displacement trong physics world; đọc Hit trước kết quả giao.',
    'Physics Overlap Box': 'Truy vấn các body chồng lấn hộp trong physics world theo bộ lọc đầu vào.',
    'Physics Overlap Capsule': 'Truy vấn các body chồng lấn capsule trong physics world theo bộ lọc đầu vào.',
    'Character Resize': 'Yêu cầu đổi kích thước capsule character. Resized cho biết thay đổi có thực hiện được tại vị trí hiện tại.',
    'Play Animation Blended': 'Chuyển sang Clip và pha trộn với clip đang chạy trong Blend giây, theo Loop và Speed.',
    'Solve Two Bone IK': 'Tính vị trí Elbow 2D từ Root, Target và độ dài hai đoạn xương. Đây là lời giải hình học, không tự áp dụng lên skeleton 3D.',
})

ARTICLES = {
    1: 'events.md', 2: 'flow-control.md', 3: 'typed-data.md', 4: 'typed-data.md',
    5: 'time.md', 6: 'functions.md', 7: 'scenes.md', 8: 'entities.md',
    9: 'scene-authoring.md', 10: 'input.md', 11: 'physics.md', 12: 'characters.md',
    13: 'animation.md', 14: 'materials.md', 15: 'camera.md', 17: 'audio.md',
    18: 'ui.md', 23: 'persistence.md',
}

OPERATIONS = {
    'Float': 'Tạo hằng số float từ Value.', 'Integer': 'Tạo hằng số int từ Value.',
    'Boolean': 'Tạo hằng số bool từ Value.', 'String': 'Tạo hằng số string từ Value.',
    'CreateArray': 'Tạo một mảng đúng kiểu từ giá trị đầu vào.',
    'ArrayAppend': 'Trả mảng mới có Item thêm ở cuối.',
    'ArrayRemoveAt': 'Trả mảng mới bỏ phần tử tại Index.',
    'ArraySet': 'Trả mảng mới thay phần tử tại Index bằng Item.',
    'ArrayFind': 'Tìm vị trí Item trong mảng; đọc kết quả chỉ số để kiểm tra có tìm thấy.',
    'ArrayReverse': 'Trả mảng mới có thứ tự phần tử đảo ngược.',
    'ArrayClear': 'Trả mảng rỗng đúng kiểu.',
    'CreateMap': 'Tạo map đúng kiểu. Khóa map là string.',
    'MapGet': 'Tra giá trị của Key trong map đúng kiểu.',
    'MapSet': 'Trả map mới có giá trị Item tại Key.',
    'MapRemove': 'Trả map mới đã bỏ Key.',
    'MapHasKey': 'Trả bool cho biết Key có trong map.',
    'MapKeys': 'Trả mảng khóa string của map.',
    'MapValues': 'Trả mảng giá trị đúng kiểu của map.',
    'MapClear': 'Trả map rỗng đúng kiểu.',
    'CreateSet': 'Tạo tập hợp đúng kiểu, không chứa phần tử trùng.',
    'SetAdd': 'Trả tập hợp mới có thêm Item nếu chưa tồn tại.',
    'SetRemove': 'Trả tập hợp mới đã bỏ Item.',
    'SetClear': 'Trả tập hợp rỗng đúng kiểu.',
    'ArrayConcat': 'Nối hai mảng cùng kiểu thành mảng mới theo thứ tự A rồi B.',
    'SortArray': 'Trả mảng được sắp xếp theo pure function so sánh được chọn bằng Callback.',
    'FilterArray': 'Trả mảng chỉ chứa các phần tử thỏa pure function điều kiện được chọn bằng Callback.',
    'MapArray': 'Áp dụng pure function Callback lên từng phần tử để tạo mảng kết quả.',
    'RandomItem': 'Chọn ngẫu nhiên một phần tử của mảng bằng luồng random hiện tại.',
    'RandomWeightedItem': 'Chọn phần tử ngẫu nhiên theo trọng số; khai báo trọng số đúng với mảng phần tử.',
    'ShuffleArray': 'Trả một hoán vị ngẫu nhiên của mảng bằng luồng random hiện tại.',
    'TruncateToInteger': 'Đổi float sang int bằng cách bỏ phần thập phân.',
    'FormatFloat': 'Chuyển float thành string theo độ chính xác đã chọn.',
    'FormatBoolean': 'Chuyển bool thành string để hiển thị.',
    'StringSplit': 'Tách chuỗi theo delimiter thành mảng string.',
    'StringReplace': 'Thay các đoạn khớp chuỗi tìm kiếm bằng chuỗi thay thế.',
    'StringJoin': 'Ghép mảng string bằng separator.',
    'EntityId': 'Trả stable ID của tham chiếu entity dưới dạng string.',
    'ReferenceEqual': 'So sánh hai tham chiếu entity có cùng danh tính hay không.',
}


@lru_cache(maxsize=1)
def index_descriptions():
    path = ROOT / 'node_index.md'
    if not path.exists():
        return {}
    return {name.strip(): description.strip() for name, description in
            re.findall(r'^- (.+?) — (.+)$', path.read_text('utf-8'), re.MULTILINE)}


def description(spec):
    name = spec.name
    if name in NOTES:
        return NOTES[name]
    if spec.variable_access:
        action = 'Đọc' if spec.variable_access == 'get' else 'Ghi'
        return f'{action} biến {spec.variable_type} trong phạm vi {spec.variable_scope or "scene"}. Name phải khớp biến đã khai báo; chọn đúng kiểu.'
    if name.startswith('Get ') and name.endswith(' Variable') or name == 'Get Variable':
        return 'Đọc biến Name đã khai báo trong Scene > Variables, trả Value đúng kiểu của node. Không thay đổi dữ liệu.'
    if name.startswith('Set ') and name.endswith(' Variable') or name == 'Set Variable':
        return 'Khi In chạy, ghi Value vào biến Name đã khai báo đúng kiểu, sau đó chạy Out. Biến giữ giá trị qua các frame.'
    if spec.kind == 'foreach':
        return 'Chụp tập dữ liệu đầu vào rồi chạy Body cho từng phần tử. Item/Index/Key chỉ có hiệu lực trong Body; Done chạy khi kết thúc. Map duyệt khóa theo thứ tự.'
    if spec.kind == 'select':
        return 'Chọn giá trị ở True hoặc False theo Condition. Đây là lựa chọn dữ liệu, không điều khiển luồng exec.'
    if 'Array Contains' in name or 'Set Contains' in name:
        return 'Trả bool cho biết tập dữ liệu có chứa Item bằng phép so sánh giá trị hay không. Không sửa tập gốc.'
    if 'Array Length' in name or 'Set Length' in name or 'Map Size' in name:
        return 'Trả số phần tử hiện có dưới dạng int. Mảng rỗng có độ dài 0; chỉ số hợp lệ nhỏ hơn độ dài.'
    if name.startswith('Slice '):
        return 'Trả mảng con từ Start (gồm) tới End (không gồm), đánh số từ 0. Không ghi lại biến gốc; dùng Set Variable nếu cần lưu.'
    if name.startswith('Insert '):
        return 'Trả bản sao mảng có Item chèn tại Index; các phần tử phía sau dịch sang phải. Ghi kết quả về biến nếu cần lưu.'
    if name.startswith('Get ') and name.endswith(' Item') and 'Map' not in name:
        return 'Đọc phần tử tại Index của mảng, đánh số từ 0. Chỉ số phải nằm trong mảng.'
    if spec.kind in ('function_call', 'pure_call'):
        return f'Gọi function {name} của dự án với các tham số bên dưới. Double-click node để xem các bước trong Function Graphs.'
    if name in index_descriptions():
        return index_descriptions()[name]
    operation = spec.function.split('<', 1)[0]
    if operation in OPERATIONS:
        note = OPERATIONS[operation]
        if operation.startswith(('Array', 'Map', 'Set', 'Create')):
            note += ' Các phép pure trả bản sao; muốn lưu thay đổi qua frame, nối kết quả vào Set Variable cùng kiểu.'
        return note
    if re.fullmatch(r'Vector[24] (Add|Subtract|Scale|Magnitude|Normalize|Dot|Distance)', name):
        operation_name = name.split(' ',1)[1]
        return {'Add':'Cộng từng thành phần A + B.', 'Subtract':'Trừ từng thành phần A - B.',
                'Scale':'Nhân từng thành phần Vector với Scale.', 'Magnitude':'Trả độ dài Euclid của Vector.',
                'Normalize':'Trả vector đơn vị cùng hướng; vector 0 cho kết quả 0.',
                'Dot':'Trả tích vô hướng A·B.', 'Distance':'Trả khoảng cách Euclid giữa A và B.'}[operation_name]
    if name in ('Make Vector2','Make Vector4'):
        return 'Ghép các thành phần đầu vào thành một vector đúng kiểu của node.'
    if spec.kind == 'event':
        return f'Nhận sự kiện {name.removeprefix("On ")} khớp cấu hình đầu vào và bắt đầu luồng Out. Dùng payload trong luồng phát ra từ sự kiện; xem tài liệu hệ thống để thiết lập đối tượng nhận.'
    for prefix, verb in [('Get ','Đọc'),('Set ','Gán/cập nhật'),('Is ','Kiểm tra điều kiện'),('Has ','Kiểm tra có'),
                         ('Create ','Tạo'),('Remove ','Xóa/gỡ'),('Stop ','Dừng'),('Pause ','Tạm dừng'),('Resume ','Tiếp tục')]:
        if name.startswith(prefix):
            arguments = ', '.join(port.name for port in spec.data_inputs) or 'trạng thái hiện tại'
            return f'{verb} {name[len(prefix):]} theo {arguments}. Kết quả và kiểu dữ liệu được ghi ở bảng IO; thiết lập tài nguyên theo tài liệu hệ thống liên quan trước khi chạy.'
    # The name states the operation; the actual signature and linked subsystem
    # manual supply its contract rather than inventing gameplay guarantees.
    operation = operation or name
    mode = {'pure': 'Tính/đọc dữ liệu khi đầu ra được sử dụng', 'event': 'Nhận sự kiện và phát luồng Out',
            'action': 'Thực hiện thao tác khi In chạy, sau đó phát Out',
            'action_result': 'Thực hiện thao tác khi In chạy và cung cấp kết quả trong luồng Out'}.get(spec.kind, 'Thực hiện quy tắc điều khiển của node')
    return f'{mode}: {name}. Thao tác native: {operation}. Các cổng và kiểu dữ liệu chính xác được liệt kê bên dưới; xem tài liệu hệ thống liên quan để thiết lập tài nguyên.'


def article(spec):
    if 'Timer' in spec.name:
        return 'timers.md'
    if 'Random' in spec.name or 'Shuffle' in spec.name:
        return 'random.md'
    if 'Sprite' in spec.name:
        return 'sprites.md'
    return ARTICLES.get(spec.category, 'feature-pipeline.md')


def md_value(value):
    return json.dumps(value, ensure_ascii=False).replace('|', '\\|').replace('\n', ' ')


def port_table(spec):
    rows = ['| Chiều | Cổng | Kiểu | Mặc định |', '| --- | --- | --- | --- |']
    for side, ports in [('IN', spec.inputs), ('OUT', spec.outputs)]:
        for port in ports:
            default = '—' if side == 'OUT' or port.type == 'exec' else f'`{md_value(port.default)}`'
            rows.append(f'| {side} | {port.name} | `{port.type}` | {default} |')
    if not spec.inputs and not spec.outputs:
        rows.append('| — | Cổng được xác định trong graph function | — | — |')
    return '\n'.join(rows)


def usage(spec):
    steps = [f'Tìm **{spec.name}** trong Node Library hoặc nhấn Tab trong graph để thêm node.']
    if spec.kind in ('function_entry', 'return'):
        steps = ['Mở Graph > Edit Function…; các cổng phụ thuộc signature của function đang mở.']
    if spec.data_inputs:
        steps.append('Chọn node, nhập hằng số ở Inspector theo bảng IN. Chuỗi nhập trực tiếp; vector/mảng nhập theo JSON, ví dụ `[1, 0, 0]`. Khai báo biến qua Scene > Scene Variables… trước khi dùng Get/Set Variable.')
    if spec.constant_inputs:
        steps.append('Các đầu vào sự kiện là cấu hình hằng số: đặt ở Inspector, không kéo dây dữ liệu vào chúng.')
    else:
        steps.append('Có thể kéo dây từ OUT dữ liệu vào IN có cùng kiểu; giá trị từ dây thay thế hằng số của cổng.')
    if any(p.type == 'exec' for p in spec.inputs):
        steps.append('Nối OUT exec của sự kiện/node trước vào IN exec; nối tiếp các OUT exec phù hợp tới bước sau.')
    elif spec.kind == 'event':
        steps.append('Nối Out tới In của action đầu tiên. Sự kiện là điểm bắt đầu, không cần nối exec từ node khác.')
    else:
        steps.append('Nối OUT dữ liệu tới node dùng kết quả. Node pure không cần dây exec.')
    if spec.kind in ('foreach', 'action_result', 'event'):
        steps.append('Dùng kết quả dữ liệu trong nhánh exec phát ra từ chính node; không lấy payload sang một sự kiện khác.')
    steps.append('Nhấn F5, thử tình huống, kiểm tra Console/Diagnostics; Shift+F5 dừng. Ctrl+S lưu thay đổi graph.')
    return '\n'.join(f'{i}. {step}' for i, step in enumerate(steps, 1))


@lru_cache(maxsize=1)
def examples():
    path = ROOT / 'docs/images/node-examples/index.json'
    return json.loads(path.read_text('utf-8')) if path.exists() else {}


def node_markdown(spec, *, preview=False):
    text = [f'# {spec.name}', f'ID `{spec.id}` · `{spec.kind}` · Workflow `{spec.workflow}`',
            description(spec), '## IO', port_table(spec),
            'Cổng `exec` điều khiển thứ tự. Cổng dữ liệu phải khớp kiểu; `vec2` không tự chuyển sang `vec3`.',
            '## Cách dùng', usage(spec)]
    if preview:
        text += ['## Hình node trong editor', '![Node thật với cổng hiện tại](help-preview:node)']
    sample = examples().get(str(spec.id))
    if sample:
        text += ['## Ví dụ từ graph thật', sample['caption'],
                 f'![Dây nối trích từ game template](images/node-examples/{spec.id}.png)',
                 f'Graph: `{sample["graph"]}` · Function: **{sample["function"]}** · Node: `{sample["node"]}`.',
                 f'[Mở hướng dẫn game](guide:{sample["guide"]})']
    text += [f'## Đọc thêm\n\n[Tài liệu hệ thống: {article(spec)}](doc:{article(spec)})']
    return '\n\n'.join(text)
