# Kết quả bàn giao hai game template — 31/10/2026

Hai template đã đạt cổng nghiệm thu native trên project hiện tại. Engine nói chung vẫn đang phát triển; kết quả này áp dụng cho hai game và các công cụ Help/Markdown được mô tả dưới đây.

| Nội dung | Flappy Bird | Isometric Snake 3D |
| --- | --- | --- |
| Gameplay | Graph native, không dùng game.py | Graph native, không dùng Python gameplay |
| Function chỉnh sửa được | 8 | 6 |
| Node instance, gồm Gameplay và function | 290 | 172 |
| Kiểm tra bốn native host | 97 đạt | 97 đạt |
| Kiểm tra editor thực tế | 22 đạt | 22 đạt |
| Kiểm tra package, chạy từ thư mục Unicode với PATH hệ thống | 21 đạt | 21 đạt |
| Replay.cmd trong thư mục template sau cài package | Đạt, khớp state và hash | Đạt, khớp state và hash |

Bốn host là node_preview, node_game, node_view và node_game_view. Bộ kiểm tra đối chiếu graph đã lưu với IR, tình huống gameplay, toàn bộ trạng thái và pixel Preview/compiled. Flappy kiểm tra điểm, va chạm sàn/cột, restart, pause và tái sử dụng cột. Snake kiểm tra ăn/tăng thân, va tường/tự cắn, chặn quay ngược, restart và pause. Ảnh hai game đã được mở kiểm tra trực quan.

Bản compiled Snake ban đầu giữ RML HUD cũ; đã build lại rồi chạy lại đủ 97 kiểm tra và đóng gói lại. Tool kiểm chứng editor cũng đã được sửa để xử lý DeferredDelete của Qt trước khi thoát; lần chạy Flappy cuối và Snake đều kết thúc thành công.

## Tài liệu và Help

- [Hướng dẫn Flappy](games/flappy-bird.md) và [Snake](games/isometric-snake.md): đủ 462 node instance, bảng IO, hằng số và mọi dây nối.
- Mỗi project có `docs/guide.md` và `docs/images/game.png`, đọc/sửa trực tiếp bằng Project Markdown.
- [Help](node-help.md) tra cứu 1.175 loại node, có tác dụng, IO, mặc định và các bước dùng; node preview đã render thử đủ 1.175 loại.
- 69 ảnh dây nối được trích bằng renderer thật từ graph hai template; ảnh gameplay lấy từ native framebuffer đã kiểm chứng.
- **File > Project Markdown… / Ctrl+Shift+M** tạo, đọc, sửa, preview và lưu `.md`, hỗ trợ ảnh tương đối trong project. Đã thử file tiếng Việt, bảng/code/ảnh, Ctrl+S, đóng/mở lại, hủy chuyển file và phát hiện file ngoài editor bị thay đổi.
- Kiểm tra UI thực tế qua F1 và menu Markdown đạt 18 kiểm tra. Bộ hồi quy đạt 120 test; kiểm tra Markdown sau chỉnh sửa cuối cũng đạt.

Pytest trên Windows có in chẩn đoán COM `0x8001010D` khi mở một số cửa sổ Qt và cảnh báo deprecation của NodeGraphQt. Các tiến trình test cuối thoát mã 0, không có assertion thất bại; kiểm chứng UI độc lập và native editor cũng hoàn tất.

## Workspace

Đã dọn hơn 26.000 file cache/thử nghiệm/trạng thái và báo cáo cũ, khoảng 10,27 GB. Các manifest/replay/mô phỏng legacy trùng trong template đã được bỏ. Giữ build đang dùng, dependency, source, tài nguyên, hướng dẫn và hai package chạy được.

Root và từng project mới/template có `.gitignore`. Quy tắc đã được kiểm tra bằng Git trong repository tạm: bỏ qua output build/generated/dist/cache/save/test, giữ graph/scene/acceptance/replay/Markdown/ảnh nguồn. Xem [cách dọn](workspace-hygiene.md).

Bằng chứng hiện tại nằm ở `artifacts/validation/template-help/`, được ignore; `summary.json` dẫn tới các báo cáo cuối. Workspace hiện chưa có `.git`; không khởi tạo Git, push hoặc deploy.

Best score của hai template chỉ giữ trong cùng phiên chơi. Các tình huống nghiệm thu không khẳng định toàn bộ tính năng engine hoặc mọi chuỗi input có thể có đã được kiểm thử.
