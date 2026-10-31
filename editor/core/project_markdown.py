"""Project-owned Markdown documents, separate from runtime/generated state."""
import os
from pathlib import Path

EXCLUDED = frozenset({'.git', '.venv', '.work', '.cache', '.pytest_cache', '__pycache__',
                      'generated', 'build', 'dist', 'deps', 'node_modules', 'artifacts'})

PROJECT_GITIGNORE = '''# Rebuildable Node_Engine project output
generated/
build/
build-*/
dist/
.cache/
.pytest_cache/
__pycache__/
*.py[cod]
*.log
*.tmp
*.dmp
# Local runtime save state
.node-engine/
saves/
save-data/
.storage.lock
slot-*.json
# Keep .nen, graphs, scenes, assets, replays, acceptance and Markdown docs.
'''


def markdown_path(root, relative):
    root = Path(root).resolve()
    candidate = Path(relative)
    path = (root / candidate).resolve()
    if not path.is_relative_to(root) or path == root or path.suffix.lower() != '.md':
        raise ValueError('Chọn file .md bên trong project hiện tại.')
    if any(part in EXCLUDED or part.startswith('build-') for part in path.relative_to(root).parts[:-1]):
        raise ValueError('Tài liệu phải nằm ngoài thư mục build/cache/generated.')
    return path


def markdown_files(root):
    root = Path(root).resolve()
    files = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('build-')
                         and not (Path(directory) / d).is_symlink())
        for name in sorted(names):
            if name.lower().endswith('.md'):
                try:
                    files.append(markdown_path(root, Path(directory) / name))
                except ValueError:
                    continue
    return sorted(files, key=lambda p: (p.name.lower() != 'readme.md', p.relative_to(root).as_posix().casefold()))


def default_readme(name):
    return f'''# {name}

Mở file `.nen` của project trong Node_Engine.

## Chạy và chỉnh sửa

1. Thêm node từ Node Library hoặc nhấn Tab trong graph.
2. Chọn node và nhấn F1 để xem tác dụng, IO, cách dùng và ví dụ.
3. Khai báo biến trong Scene > Scene Variables… rồi nối các cổng cùng kiểu.
4. Nhấn F5 để Play, F6 Pause, Shift+F5 Stop. Ctrl+S lưu project.

## Tài liệu của project

Mở **File > Project Markdown…** (Ctrl+Shift+M) để đọc, tạo và sửa `.md`.
Chọn **New .md** rồi nhập `docs/notes.md`. Ctrl+S trong cửa sổ Markdown lưu tài liệu.
Khung Preview hiển thị tiêu đề, danh sách, bảng, code và ảnh theo đường dẫn tương đối.

```markdown
![Ví dụ ảnh](assets/example.png)
[Mở ghi chú](docs/notes.md)
```

Đường dẫn tính từ thư mục chứa file Markdown. Lưu ảnh vào project trước khi chèn.
File `.md` và ảnh hướng dẫn là dữ liệu nguồn cần giữ khi chia sẻ project.
`generated/`, `build/`, `dist/` và cache là đầu ra có thể tạo lại.
'''
