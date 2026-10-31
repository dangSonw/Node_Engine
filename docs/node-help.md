# Node_Engine Help

Chọn một node rồi nhấn **F1**, hoặc mở **Help > Node Help…**. Nút **Node Help / IO / Examples…** ở Inspector mở đúng node. Trong Function Graphs cũng có **Node Help (F1)**.

Gõ tên, stable type ID hoặc kiểu cổng vào ô tìm kiếm. Chọn nhóm để lọc. Mỗi trang có tác dụng, IO, giá trị mặc định, các bước sử dụng và hình node thật được vẽ từ signature hiện tại. Ví dụ có dây nối lấy từ các graph game đã kiểm chứng.

## Hai game mẫu

- [Flappy Bird: dựng game và từng node](games/flappy-bird.md)
- [Isometric Snake 3D: dựng game và từng node](games/isometric-snake.md)
- [Tham chiếu 1.175 node builtin](node-reference.md)

Hướng dẫn game có toàn bộ entity, tài nguyên, biến, RML, signature function, từng node và mọi dây nối. Hai game dùng chung compiler/runtime native với project của bạn.

## Viết và đọc Markdown của project

1. Mở một project `.nen`.
2. Chọn **File > Project Markdown…** hoặc **Ctrl+Shift+M**.
3. Chọn `README.md`, `docs/guide.md` hoặc file `.md` bất kỳ trong danh sách.
4. Sửa nội dung ở giữa; Preview bên phải cập nhật sau khi gõ.
5. Chọn **New .md**, nhập ví dụ `docs/notes.md` để tạo file.
6. Nhấn **Ctrl+S** trong cửa sổ Markdown hoặc nút **Save** để lưu.
7. Đóng rồi mở lại để đọc bản đã lưu. Nếu nội dung chưa lưu, cửa sổ hỏi Save/Discard/Cancel khi chuyển file hoặc đóng.

Project mới có `README.md` hướng dẫn sẵn. Hai template có `docs/guide.md` và ảnh gameplay trong `docs/images/game.png`. Tài liệu là file thật của project, có thể sửa bằng công cụ khác và chia sẻ cùng `.nen`.

```markdown
# Ghi chú gameplay

## Điều khiển

- Space: nhảy
- R: chơi lại

| Node | Tác dụng |
| --- | --- |
| Branch | Chọn nhánh True hoặc False |

![Ảnh game](images/game.png)
[Đọc README](../README.md)
```

Đường dẫn ảnh/link tính từ thư mục chứa file `.md`. Ảnh phải nằm trong project. Link `.md` mở trong cùng công cụ; link website mở khi bấm. Markdown hỗ trợ tiêu đề, bảng, danh sách, code và ảnh. File nguồn UTF-8, không cần cài Markdown viewer khác.

## Hiểu cổng node

- `exec`: điều khiển thứ tự thực thi. Nối đầu ra sự kiện/action tới đầu vào action tiếp theo.
- Cổng dữ liệu: giá trị phải đúng kiểu. Không nối trực tiếp int sang float hay vec2 sang vec3; dùng node chuyển đổi hoặc Make Vector phù hợp.
- Hằng số: chọn node và điền Inspector. Dây vào cổng dữ liệu thay thế hằng số của cổng đó.
- Pure: tính giá trị khi có nơi dùng kết quả; không cần exec.
- Event: là điểm bắt đầu luồng. Filter/Receiver của event là cấu hình hằng số.
- Payload/Item/Index: dùng trong chính nhánh Out/Body tạo chúng; không đọc từ sự kiện độc lập khác.
- Function Input/Output: cổng phụ thuộc signature của function đang mở. Help lấy signature thật từ project, gồm cả function/type/component do bạn tạo.

Xem [dữ liệu, file sinh ra và dọn workspace](workspace-hygiene.md).
