# Hướng dẫn cài đặt ALEX trên Ubuntu (LAN — nhiều người dùng)

**Phiên bản tài liệu:** 2026-05 · ALEX v0.3  
**Môi trường mục tiêu:** Máy Ubuntu công ty, IP LAN **`10.88.152.11`**  
**URL truy cập:** **`http://10.88.152.11:8765/login`**

**Đăng nhập admin (mặc định team — sau khi tạo user trên server):**

| | |
|---|---|
| Username | `admin` |
| Password | `Alex@2025!` *(có dấu `!` ở cuối)* |

> Mật khẩu trên chỉ đúng nếu IT đã chạy lệnh tạo admin như mục **§6**. Ubuntu server **mới cài** chưa có user — phải tạo admin trước khi login. **Đổi mật khẩu** sau lần đăng nhập đầu trên môi trường công ty.

Tài liệu này dành cho **IT / admin** cài server và **engineer Windows** chỉ cần mở trình duyệt.

---

## 1. Tổng quan

```text
                    Mạng LAN công ty (10.88.x.x)
┌──────────────────────────────────────────────────────────┐
│  PC Ubuntu — 10.88.152.11  (SERVER — cài ALEX 1 lần)      │
│  • Python + ALEX                                          │
│  • Port 8765 (HTTP)                                       │
│  • Ollama (tuỳ chọn, chạy local trên cùng máy)           │
│  • Dữ liệu: web_data/uploads/{user}/, output/{user}/       │
└────────────────────────────┬─────────────────────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
 Windows PC 1            Windows PC 2            Ubuntu khác
 Chrome / Edge            (chỉ browser)            (browser)
 http://10.88.152.11:8765/login
```

| Thành phần | Ai cài? | Ghi chú |
|------------|---------|---------|
| ALEX server | IT trên Ubuntu `10.88.152.11` | Clone repo, `config.ubuntu.yaml`, systemd |
| Trình duyệt | Mỗi engineer | **Không** cài Python trên Windows |
| Tài khoản đăng nhập | Admin tạo trên server | `admin` + các user `engineer` |
| M365 Copilot | Mỗi engineer (tab Review) | Token lưu trên server theo user |

---

## 2. Yêu cầu hệ thống (Ubuntu server)

| Hạng mục | Yêu cầu |
|----------|---------|
| OS | Ubuntu 20.04 / 22.04 LTS (64-bit) |
| RAM | ≥ 8 GB (16 GB nếu chạy Ollama local) |
| Ổ đĩa | ≥ 20 GB trống (spec + job output) |
| Python | 3.9 trở lên |
| Mạng | IP tĩnh hoặc DHCP reservation: **10.88.152.11** |
| Port | **TCP 8765** mở cho subnet LAN (ví dụ `10.88.0.0/16`) |
| Tuỳ chọn | `tesseract-ocr`, `git`, `curl` |

---

## 3. Cài đặt nhanh (script tự động)

Trên máy Ubuntu **`10.88.152.11`**:

```bash
# 1. Cài package hệ thống
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl tesseract-ocr

# 2. Clone mã nguồn (hoặc copy folder từ USB nội bộ)
sudo mkdir -p /opt/alex
sudo chown "$USER:$USER" /opt/alex
cd /opt/alex
git clone https://github.com/CrazyFox21699/SyS_Spec_GenAI.git
cd SyS_Spec_GenAI/pm_test_spec_assistant

# 3. Chạy script cài đặt
chmod +x scripts/install_ubuntu_server.sh
./scripts/install_ubuntu_server.sh
```

Script sẽ:

1. Tạo virtualenv `.venv`
2. `pip install -r requirements.txt`
3. Copy `config.ubuntu.yaml` → `config.yaml`
4. Hỏi tạo tài khoản **admin**
5. In URL LAN và lệnh firewall

---

## 4. Cài đặt thủ công (từng bước)

### Bước 4.1 — Virtualenv và dependency

```bash
cd /opt/alex/SyS_Spec_GenAI/pm_test_spec_assistant
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 4.2 — Áp config Ubuntu LAN

```bash
./scripts/use_ubuntu_config.sh
```

File `config.ubuntu.yaml` đã cấu hình sẵn:

```yaml
deployment:
  mode: production      # analyze qua worker — nhiều user ổn định
  host: 0.0.0.0         # lắng nghe mọi card mạng (LAN)
  port: 8765
  lan_ipv4: 10.88.152.11
  public_url: http://10.88.152.11:8765

team_auth:
  enabled: true         # bắt buộc đăng nhập — mỗi user job riêng

security:
  rate_limit_per_minute: 600   # tránh 429 khi nhiều người poll API

assist:
  copilot:
    enabled: false      # GitHub Copilot CLI không dùng chung 1 server
```

**Nếu IP server khác** — sửa `lan_ipv4` và `public_url` trong `config.ubuntu.yaml`, chạy lại `use_ubuntu_config.sh`.

### Bước 4.3 — Tạo tài khoản admin

```bash
source .venv/bin/activate
python scripts/reset_team_auth.py --yes --username admin
# Nhập password mới (tối thiểu 8 ký tự)
```

Tạo thêm engineer:

```bash
python scripts/create_team_user.py --username nguyen --role engineer
python scripts/create_team_user.py --username tanaka --role engineer
```

### Bước 4.4 — M365 (tuỳ chọn)

Sửa `config.yaml`:

```yaml
assist:
  m365:
    enabled: true
    client_id: "<Azure Application Client ID>"
    tenant_id: "<tenant-id-hoặc-common>"
```

Chi tiết IT: [IT_ADMIN_M365_SETUP.md](IT_ADMIN_M365_SETUP.md) · [M365_COPILOT_ACTIVATION_GUIDE.md](M365_COPILOT_ACTIVATION_GUIDE.md)

### Bước 4.5 — Firewall

```bash
# Chỉ cho phép LAN công ty (điều chỉnh subnet theo IT)
sudo ufw allow from 10.88.0.0/16 to any port 8765 proto tcp comment 'ALEX LAN'
sudo ufw enable
sudo ufw status
```

**Không** cần NAT port-forward nếu client và server **cùng VLAN** `10.88.x.x`.

Kiểm tra trên server:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/login
# Kỳ vọng: 200
```

Kiểm tra từ Windows (PowerShell):

```powershell
Test-NetConnection -ComputerName 10.88.152.11 -Port 8765
Start-Process "http://10.88.152.11:8765/login"
```

---

## 5. Chạy server

### 5.1 — Một terminal (dev / thử nhanh)

```bash
cd /opt/alex/SyS_Spec_GenAI/pm_test_spec_assistant
source .venv/bin/activate
./scripts/start_alex_team.sh
```

Một lệnh khởi động: **Ollama** (nếu có) + **worker** + **web UI**. `Ctrl+C` dừng tất cả.

Console in:

```text
LAN URL: http://10.88.152.11:8765/
Team login: http://10.88.152.11:8765/login
```

### 5.2 — Systemd (production — khuyến nghị)

Sau khi chạy `./scripts/install_ubuntu_server.sh`, hoặc thủ công:

```bash
sudo cp scripts/systemd/alex-web.service /etc/systemd/system/
sudo cp scripts/systemd/alex-worker.service /etc/systemd/system/
# Sửa User= và WorkingDirectory= trong file nếu đường dẫn khác /opt/alex/...

sudo systemctl daemon-reload
sudo systemctl enable alex-web alex-worker
sudo systemctl start alex-web alex-worker
sudo systemctl status alex-web alex-worker
```

Xem log:

```bash
journalctl -u alex-web -f
journalctl -u alex-worker -f
```

### 5.3 — Ollama (tuỳ chọn, trên cùng Ubuntu)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:latest
sudo systemctl enable ollama
sudo systemctl start ollama
```

Ollama chỉ bind `127.0.0.1:11434` — engineer **không** truy cập trực tiếp; ALEX gọi nội bộ.

---

## 6. Đăng nhập (Login)

### 6.1 Tạo / đặt lại tài khoản admin (trên Ubuntu server)

Chạy **một lần** sau cài đặt (trên máy `10.88.152.11`):

```bash
cd /opt/alex/SyS_Spec_GenAI/pm_test_spec_assistant   # đường dẫn thực tế của bạn
source .venv/bin/activate

# Tạo admin với mật khẩu team mặc định (xóa user cũ nếu có)
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'
```

Hoặc nhập password tương tác (không lộ trên màn hình):

```bash
python scripts/reset_team_auth.py --yes --username admin
# Nhập password mới ≥ 8 ký tự, xác nhận lại
```

Tạo thêm engineer:

```bash
python scripts/create_team_user.py --username ten_ban --role engineer
# Nhập password cho từng người
```

### 6.2 Thông tin đăng nhập

| Vai trò | URL | Username | Password (mặc định team) |
|---------|-----|----------|---------------------------|
| Admin | http://10.88.152.11:8765/login | `admin` | `Alex@2025!` |
| Engineer | http://10.88.152.11:8765/login | do admin cấp | do admin cấp |
| Admin console | http://10.88.152.11:8765/admin | `admin` | cùng password admin |

**Lưu ý mật khẩu:** đúng là **`Alex@2025!`** (chữ A hoa, có `@` và **`!` cuối**), **không** phải `Alex@2025`.

### 6.3 Các bước login (Ubuntu server hoặc Windows LAN)

1. Mở trình duyệt (Firefox / Chrome trên Ubuntu, hoặc Chrome / Edge trên Windows).
2. Vào **`http://10.88.152.11:8765/login`**
   - Trang login hiện dòng xanh: `Team server · http://10.88.152.11:8765` nếu config Ubuntu đúng.
3. Nhập:
   - **Username:** `admin`
   - **Password:** `Alex@2025!`
4. Bật **Remember me** nếu muốn giữ session ~30 ngày (cấu hình `remember_days` trong config).
5. Bấm **LOGIN** → chuyển sang tab **Spec review**.
6. (Admin) Quản lý user: mở tab mới → **`http://10.88.152.11:8765/admin`** → Create user / Reset password.

### 6.4 Sau khi login

| Bước | Tab | Việc làm |
|------|-----|----------|
| 1 | **Review** | Upload spec → **Review specification** |
| 2 | **Logic & Definitions** | Xem cây logic, trace definition |
| 3 | **Final File** | Export Excel |
| Sign out | Góc phải top bar | **Sign out** |

M365 (tuỳ chọn): tab **Review** → **Sign in M365** — mỗi user đăng nhập Microsoft riêng.

### 6.5 Quên mật khẩu

| Ai | Cách xử lý |
|----|------------|
| Engineer | Admin reset tại `/admin` → **Reset password** |
| Admin | Trên Ubuntu SSH: `python scripts/reset_team_auth.py --yes --username admin --password 'MatKhauMoi!' ` |
| Không login được | Kiểm tra server đang chạy: `systemctl status alex-web` hoặc `./scripts/start_alex_team.sh` |

---

## 7. Hướng dẫn engineer (Windows / LAN)

### 7.1 Không cần cài gì

| Cần | Không cần |
|-----|-----------|
| Chrome hoặc Edge | Python, Git, Node |
| Cùng LAN với server | VPN (trừ khi IT yêu cầu) |
| Username/password do admin cấp | Quyền admin Windows |

### 7.2 Truy cập

1. Mở browser → **`http://10.88.152.11:8765/login`**
2. Đăng nhập — admin dùng `admin` / `Alex@2025!`; engineer dùng tài khoản admin đã cấp
3. Tab **Review** → upload file spec → **Review specification**
4. Tab **Logic & Definitions** → trace, Copilot brief, sửa definition
5. Tab **Final File** → export Excel

**Shortcut Desktop (Windows):**

- Chuột phải Desktop → New → Shortcut  
- Target: `"C:\Program Files\Google\Chrome\Application\chrome.exe" http://10.88.152.11:8765/login`  
- Name: `ALEX Spec Review`

### 7.3 Quy tắc dùng chung server

- Mỗi người **job riêng** — không thấy job của người khác (trừ admin).
- Upload spec **confidential** chỉ nằm trên server Ubuntu — không copy ra USB tùy tiện.
- Tab **Library** trỏ folder **trên Ubuntu server**, không phải ổ `C:` Windows.
- M365: mỗi người **Sign in** riêng trên tab Review.

---

## 8. Quản trị (admin)

| Việc | Cách làm |
|------|----------|
| URL admin | `http://10.88.152.11:8765/admin` (không có link sidebar) |
| Tạo user | Admin console → Create user |
| Reset password | Admin console → Reset password |
| Quên pass admin | Trên server: `python scripts/reset_team_auth.py --yes --username admin` |
| Backup | Copy `web_data/alex_users.db`, `web_data/uploads/`, `web_data/output/` |
| Cập nhật code | `git pull` → `systemctl restart alex-web alex-worker` |

---

## 9. Cơ chế multi-user (kỹ thuật)

ALEX đã bật sẵn khi `deployment.mode: production` + `team_auth.enabled: true`:

| Tài nguyên | Cách tách |
|------------|-----------|
| Upload | `web_data/uploads/{username}/` |
| Job output | `web_data/output/{username}/{job_id}/` |
| M365 token | `web_data/users/{username}/m365/` |
| Session cookie | `alex_session`, `SameSite=Lax`, `path=/` — hoạt động với IP LAN |
| Analyze queue | `web.worker` xử lý tuần tự — tránh treo web UI |

Mỗi client LAN có IP riêng → rate limit tính **theo IP** (mặc định 600 req/phút/IP).

---

## 10. Xử lý sự cố

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| Windows không mở được trang | Firewall / sai VLAN | `ping 10.88.152.11`; IT mở TCP 8765 |
| `502` / không phản hồi | Service chưa chạy | `systemctl start alex-web alex-worker` |
| Analyze treo mãi | Worker down | `systemctl status alex-worker` |
| `429 Rate limit` | Quá nhiều tab | Tăng `rate_limit_per_minute` trong config |
| Login OK, API 401 | Cookie / hết session | Đăng nhập lại; kiểm tra truy cập đúng IP (không mix localhost vs LAN) |
| Upload > 50 MB fail | Giới hạn config | Tăng `security.max_upload_mb` |

---

## 11. Checklist triển khai

- [ ] Ubuntu có IP **10.88.152.11** trên LAN
- [ ] `config.yaml` từ `config.ubuntu.yaml` (`host: 0.0.0.0`, `mode: production`)
- [ ] Firewall mở **8765** cho subnet LAN
- [ ] Admin login OK: `admin` / `Alex@2025!` tại http://10.88.152.11:8765/login
- [ ] `alex-web` + `alex-worker` running (systemd hoặc `start_alex_team.sh`)
- [ ] Windows test: `http://10.88.152.11:8765/login` → login → analyze mẫu
- [ ] 2 user test: user A không thấy job user B
- [ ] IT backup `web_data/` định kỳ

---

## 12. Tài liệu liên quan

| File | Nội dung |
|------|----------|
| [LAN_UBUNTU_WINDOWS_DEPLOY.md](LAN_UBUNTU_WINDOWS_DEPLOY.md) | Bản tiếng Anh, cùng nội dung |
| [TEAM_SERVER_DEPLOY.md](TEAM_SERVER_DEPLOY.md) | Team auth, worker, isolation |
| [COMPANY_DEPLOYMENT.md](COMPANY_DEPLOYMENT.md) | Sanitize trước khi đưa lên máy công ty |
| [IT_ADMIN_M365_SETUP.md](IT_ADMIN_M365_SETUP.md) | Azure app |
| `config.ubuntu.yaml` | Config mẫu LAN |
| `scripts/install_ubuntu_server.sh` | Cài tự động |
| `scripts/start_alex_team.sh` | Chạy 1 terminal |

---

**Liên hệ IT nội bộ** khi cần mở port firewall hoặc đăng ký Azure M365 app.
