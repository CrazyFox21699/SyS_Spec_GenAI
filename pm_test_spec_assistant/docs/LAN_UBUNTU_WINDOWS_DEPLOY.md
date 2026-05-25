# ALEX — Ubuntu server + Windows clients (cùng LAN)

Hướng dẫn triển khai **một máy Ubuntu** làm server ALEX; mọi máy **Windows** trên cùng VLAN/LAN truy cập qua trình duyệt (không cần cài Python trên Windows).

**Ví dụ IP server:** `10.88.152.11`  
**URL cho engineer:** `http://10.88.152.11:8765/login`

---

## Kiến trúc

```text
┌─────────────────────────────────────────────────────────┐
│  Ubuntu server 10.88.152.11                             │
│  • run_web.py (port 8765, bind 0.0.0.0)                 │
│  • web.worker (production analyze queue)                │
│  • Ollama (optional, localhost:11434)                   │
│  • web_data/ — uploads + jobs theo từng user            │
└───────────────────────────┬─────────────────────────────┘
                            │ LAN 10.88.x.x
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   Windows PC A         Windows PC B         Windows PC C
   Chrome / Edge        (chỉ trình duyệt)    đăng nhập riêng
```

- **Không** cài ALEX trên từng máy Windows — chỉ mở browser.
- Mỗi engineer có **tài khoản ALEX riêng** (`team_auth`); job/upload tách biệt.
- M365: mỗi người **Sign in M365** trên tab Review (token lưu theo user trên server).

---

## Phần 1 — Cài trên Ubuntu server (IT / admin)

### 1.1 Yêu cầu

- Ubuntu 20.04+ (22.04 LTS khuyến nghị)
- Python 3.9+
- Git, `pip`, `venv`
- Port **8765** mở trên firewall **chỉ cho subnet LAN** (ví dụ `10.88.0.0/16`)
- (Tuỳ chọn) Tesseract OCR: `sudo apt install tesseract-ocr`

### 1.2 Clone và cài dependency

```bash
cd /opt   # hoặc thư mục công ty cho phép
git clone https://github.com/CrazyFox21699/SyS_Spec_GenAI.git
cd SyS_Spec_GenAI/pm_test_spec_assistant

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Trước khi đưa lên máy công ty, chạy (trên máy dev):

```bash
python scripts/sanitize_for_company_deploy.py
```

Chi tiết: [COMPANY_DEPLOYMENT.md](COMPANY_DEPLOYMENT.md).

### 1.3 Sửa `config.yaml` (bắt buộc cho LAN)

```yaml
deployment:
  mode: production          # bắt buộc chạy worker riêng
  host: 0.0.0.0             # lắng nghe mọi interface LAN
  port: 8765

team_auth:
  enabled: true
  session_hours: 12
  cookie_secure: false      # true nếu sau này có HTTPS reverse proxy

security:
  enabled: true
  require_token: false
  max_upload_mb: 50
  rate_limit_per_minute: 600   # nhiều user LAN poll API — tăng từ 120

assist:
  copilot:
    enabled: false          # Copilot CLI không multi-user trên 1 server
  m365:
    enabled: true
    client_id: "<Azure-App-Client-ID>"
    tenant_id: common       # hoặc tenant công ty
  ollama:
    base_url: http://127.0.0.1:11434

llm:
  base_url: http://127.0.0.1:11434
```

**Không** đặt `host: 10.88.152.11` — dùng `0.0.0.0` để bind tất cả NIC; engineer truy cập bằng IP LAN.

### 1.4 Tạo tài khoản team

```bash
source .venv/bin/activate
python scripts/create_team_user.py --username admin --role admin
python scripts/create_team_user.py --username engineer1 --role engineer
python scripts/create_team_user.py --username engineer2 --role engineer
```

### 1.5 Firewall Ubuntu

```bash
# Chỉ cho phép LAN (điều chỉnh subnet theo IT công ty)
sudo ufw allow from 10.88.0.0/16 to any port 8765 proto tcp
sudo ufw enable
sudo ufw status
```

Nếu công ty dùng `iptables` / firewall tập trung — mở **TCP 8765** tới IP `10.88.152.11` từ VLAN engineer.

**NAT / direct LAN:** Trong cùng subnet `10.88.x.x`, Windows ping được server:

```powershell
ping 10.88.152.11
```

Không cần port-forward NAT nếu client và server **cùng LAN**. NAT chỉ cần khi truy cập từ **ngoài** mạng công ty (thường IT không khuyến khích cho tool nội bộ).

### 1.6 Chạy thử (2 terminal)

**Terminal 1 — Web UI**

```bash
cd /opt/SyS_Spec_GenAI/pm_test_spec_assistant
source .venv/bin/activate
python run_web.py
```

Console sẽ in:

```text
Starting ALEX at http://0.0.0.0:8765/
LAN URL: http://10.88.152.11:8765/
Team login: http://10.88.152.11:8765/login
Analyze mode: production — also run: python -m web.worker
```

**Terminal 2 — Worker**

```bash
cd /opt/SyS_Spec_GenAI/pm_test_spec_assistant
source .venv/bin/activate
python -m web.worker
```

**(Tuỳ chọn) Terminal 3 — Ollama**

```bash
ollama serve
ollama pull qwen2.5:latest
```

Hoặc dùng script:

```bash
chmod +x scripts/start_alex_team.sh
./scripts/start_alex_team.sh
```

### 1.7 Chạy nền với systemd (khuyến nghị production)

Tạo user service `alex` hoặc chạy dưới user deploy. Ví dụ `/etc/systemd/system/alex-web.service`:

```ini
[Unit]
Description=ALEX web UI
After=network.target

[Service]
Type=simple
User=alex
WorkingDirectory=/opt/SyS_Spec_GenAI/pm_test_spec_assistant
Environment=PATH=/opt/SyS_Spec_GenAI/pm_test_spec_assistant/.venv/bin
ExecStart=/opt/SyS_Spec_GenAI/pm_test_spec_assistant/.venv/bin/python run_web.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/alex-worker.service` — tương tự với `ExecStart=... python -m web.worker`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now alex-web alex-worker
sudo systemctl status alex-web
```

### 1.8 Admin console (IT)

Sau khi đăng nhập `admin`:

`http://10.88.152.11:8765/admin`

Tạo user, reset password, disable account (không có link công khai trên sidebar).

---

## Phần 2 — Máy Windows (engineer, không cài server)

### 2.1 Yêu cầu trên Windows

| Cần | Không cần |
|-----|-----------|
| Chrome hoặc Edge mới | Python, Node, Git |
| Cùng LAN với `10.88.152.11` | Cài `@github/copilot` CLI |
| Tài khoản ALEX do admin cấp | Azure CLI |

### 2.2 Truy cập lần đầu

1. Mở browser → `http://10.88.152.11:8765/login`
2. Đăng nhập username/password (admin đã tạo).
3. Tab **Review** → upload spec hoặc **Load sample package** (nếu admin đã copy sample lên server).
4. **Review specification** → đợi analyze xong.
5. Tab **Logic & Definitions**, **Diagram**, **Final File** như trên Mac.

### 2.3 Shortcut trên Windows (tuỳ chọn)

Tạo shortcut Desktop:

- **Target:** `"C:\Program Files\Google\Chrome\Application\chrome.exe" http://10.88.152.11:8765/login`
- **Name:** ALEX Spec Review

Hoặc pin tab trong Edge cho team.

### 2.4 M365 trên Windows client

- Mỗi engineer bấm **Sign in M365** trên server UI (OAuth device code mở tab Microsoft).
- Token lưu trên **server** tại `web_data/users/{username}/m365/` — không lưu trên PC Windows.
- Account cần license **Microsoft 365 Copilot** (work/school). Xem [M365_COPILOT_ACTIVATION_GUIDE.md](M365_COPILOT_ACTIVATION_GUIDE.md).
- Nếu không có license API: dùng **Paste from Copilot Web** hoặc Ollama trên server.

### 2.5 Lỗi thường gặp (Windows client)

| Triệu chứng | Nguyên nhân | Xử lý |
|-------------|-------------|--------|
| Không mở được trang | Firewall / sai VLAN | `ping 10.88.152.11`; nhờ IT mở TCP 8765 |
| `429 Rate limit` | Nhiều tab poll API | IT tăng `rate_limit_per_minute` trên server |
| Analyze treo | Worker chưa chạy | IT: `systemctl status alex-worker` |
| Login OK nhưng 401 API | Session hết hạn | Đăng nhập lại `/login` |
| Upload fail | File > 50 MB | Tăng `security.max_upload_mb` |

---

## Phần 3 — Kiểm tra nhanh (IT)

Trên **Ubuntu server**:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/login
# kỳ vọng: 200
```

Trên **Windows** (PowerShell):

```powershell
Test-NetConnection -ComputerName 10.88.152.11 -Port 8765
Invoke-WebRequest -Uri "http://10.88.152.11:8765/login" -UseBasicParsing | Select-Object StatusCode
```

Checklist multi-user:

1. Tạo 2 engineer → user A analyze → user B **không** thấy job của A.
2. Cả hai truy cập cùng lúc từ 2 PC Windows.
3. Backup định kỳ: `web_data/output/`, `web_data/uploads/`, `web_data/alex_users.db`.

---

## Bảo mật (khuyến nghị IT)

- Chỉ mở port 8765 **trong LAN** — không expose ra internet nếu không bắt buộc.
- Sau này: Nginx + HTTPS nội bộ → `team_auth.cookie_secure: true`.
- Spec khách hàng chỉ nằm trên server `web_data/` — không sync ra từng laptop Windows.
- Azure `client_id` đặt trong `config.yaml` trên server; không commit secret lên Git.

---

## Tài liệu liên quan

| Doc | Nội dung |
|-----|----------|
| [TEAM_SERVER_DEPLOY.md](TEAM_SERVER_DEPLOY.md) | Team auth, worker, isolation chi tiết |
| [COMPANY_DEPLOYMENT.md](COMPANY_DEPLOYMENT.md) | Sanitize trước khi copy sang máy công ty |
| [IT_ADMIN_M365_SETUP.md](IT_ADMIN_M365_SETUP.md) | Azure app registration |
| [M365_COPILOT_ACTIVATION_GUIDE.md](M365_COPILOT_ACTIVATION_GUIDE.md) | License Copilot cho engineer |
