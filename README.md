# FB Group Auto-Poster

Ứng dụng tự động đăng bài lên Facebook Groups.

## Yêu cầu
- Python 3.10+
- Node.js 18+ (LTS)

## Cài đặt lần đầu

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\playwright install chromium
```

### Frontend
```bash
cd frontend
npm install
```

## Khởi động

### Cách 1: Double-click `start.bat` (Windows)

### Cách 2: Thủ công

**Terminal 1 – Backend:**
```bash
cd backend
venv\Scripts\uvicorn main:app --reload --port 8000
```

**Terminal 2 – Frontend:**
```bash
cd frontend
npm run dev
```

Mở trình duyệt: **http://localhost:5173**

## Tính năng
- ✅ Quản lý nhiều tài khoản Facebook
- ✅ Quản lý nhiều nhóm Facebook
- ✅ Đăng bài với text, hình ảnh, link
- ✅ Đăng bài ngay lập tức hoặc lên lịch
- ✅ Xem lịch sử đăng bài

## Lưu ý
- Mật khẩu được lưu dạng plaintext trong `backend/data/accounts.json` (chỉ dùng local)
- Mặc định trình duyệt sẽ hiện lên để bạn xử lý 2FA nếu cần
- Bật **Headless** nếu muốn chạy ẩn (không hiện trình duyệt)
