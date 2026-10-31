# Source, file sinh ra và dọn workspace

## File cần giữ/chia sẻ

- Source editor/runtime/tools/tests, CMake, registry và các file khóa dependency.
- `.nen`, graph, scene, prefab, sprite/material/UI, mesh/texture/audio nguồn.
- `acceptance.json`, `replays/*.json`: dữ liệu đầu vào kiểm thử có chủ đích, cần lưu cùng game.
- `README.md`, `docs/*.md`, `docs/images/`: tài liệu và ảnh ví dụ đã chọn cho người dùng.
- `runtime/generated/adapters.generated.cpp`: adapter native dùng bởi CMake, CLI tái sinh từ registry.

## Đầu ra được .gitignore loại trừ

| Vị trí | Nội dung | Cách tạo lại |
| --- | --- | --- |
| `.venv/`, `deps/` | Môi trường và dependency cài cục bộ | Theo README và docs/dependencies.md |
| `build/`, `build-*/` | Native executable, object, CMake/Ninja cache | tools/build.ps1 |
| `generated/` trong project | IR, C++, preview, build request | Export C++ hoặc Build Game |
| `dist/` trong project | Game đóng gói | Verify rồi tools/package_template_games.py |
| `.cache/`, `.work/` | Bản thử, project tạm, cache build, file AI kiểm tra | Các lệnh verify/test tương ứng |
| `artifacts/validation/` | Log, state JSON, ảnh chụp, báo cáo kiểm chứng | Các tool verify; không phải source gameplay |
| `artifacts/demos/` | Package demo có thể chạy | Tool package tương ứng |
| `__pycache__/`, `.pytest_cache/` | Cache Python/pytest | Tự tạo khi chạy Python/test |
| `saves/`, `save-data/`, `slot-*.json`, `.storage.lock` | Trạng thái save cục bộ | Runtime save/load |

Root `.gitignore` giữ JSON nguồn và ảnh hướng dẫn; không ignore toàn bộ `*.json` hay `*.png`. Project mới và hai template có `.gitignore` riêng để chia sẻ độc lập. Nếu source đã được Git theo dõi từ trước, thêm ignore không tự bỏ theo dõi; kiểm tra trạng thái Git trong repository của bạn.

## Dọn thực tế

```powershell
.venv/Scripts/python.exe -X utf8 tools/clean_workspace.py
.venv/Scripts/python.exe -X utf8 tools/clean_workspace.py --apply --report artifacts/validation/template-help/cleanup.json
```

Lệnh đầu chỉ liệt kê. Lệnh thứ hai xóa các đầu ra cũ được xác định trong tool: cache, thử nghiệm `.work`, báo cáo validation cũ, Python cache và các bản mô phỏng/manifest/replay legacy đã được `.nen`/acceptance/replays hiện tại thay thế. Tool kiểm tra đường dẫn nằm trong workspace và từ chối symlink/junction ở đích xóa.

Mặc định giữ build Flappy hiện tại trong `.work/build-template-flappy` và bằng chứng lần bàn giao ở `artifacts/validation/template-help`. Dùng `--keep đường/dẫn` để giữ thêm đầu ra. Giữ root `build`, dependency, môi trường, package demo và `dist` hai game để tiếp tục chạy được.

Save runtime mặc định dùng `SDL_GetPrefPath("NodeEngine", game)` ở vùng dữ liệu người dùng Windows; `--save-root` dùng để đặt thư mục khác khi test. Tool dọn workspace không chạm dữ liệu save bên ngoài workspace và không thay đổi lịch sử project/QSettings.

Thư mục làm việc lần này chưa có `.git`; các quy tắc đã được chuẩn bị và kiểm tra bằng Git trong repository tạm. Tool không tự khởi tạo repository, push hay deploy.
