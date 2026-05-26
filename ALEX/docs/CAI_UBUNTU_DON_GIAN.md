# Cài ALEX trên Ubuntu — hướng dẫn ngắn

**Đường dẫn cố định trên server:** `/home/tmc_ai_common/ALEX`

**Quy tắc vàng:** Copy **cả folder ALEX** (git pull hoặc ZIP). **Không** copy lẻ 1–2 file từ GitHub.

---

## Trước khi cài — nhờ IT (1 lần)

| IT cấp | Bạn đặt ở đâu |
|--------|----------------|
| File **root CA** (`.pem`) | `config/company-ca.pem` |
| **client_id**, **tenant_id** | `config.yaml` |
| **Secret Value** (Azure) | `.env` → `M365_CLIENT_SECRET=` |
| Mở port **8765** LAN | `sudo ufw allow 8765/tcp` |

Mẫu email gửi IT: [IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md)

---

## Cài lần đầu — 3 bước

### Bước 1 — Đưa code lên server

**Cách A — Git (khuyến nghị):**
```bash
cd /home/tmc_ai_common/ALEX
git pull origin main
```

**Cách B — ZIP:**
```bash
cd /home/tmc_ai_common
unzip -o ALEX.zip   # giải nén đè, giữ web_data/ và .env nếu đã có
cd ALEX
```

### Bước 2 — Chạy 1 lệnh cài đặt

```bash
cd /home/tmc_ai_common/ALEX
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

Script tự: cài Python, sửa IP trong `config.yaml`, tạo `.venv`, tạo user `admin`.

### Bước 3 — Điền secret + CA, rồi chạy

```bash
# 1) CA từ IT
cp /path/from/it/root-ca.pem config/company-ca.pem

# 2) Sửa .env
nano .env
```

Nội dung `.env` tối thiểu:
```
M365_CLIENT_SECRET=paste-Value-tu-Azure-o-day
REQUESTS_CA_BUNDLE=/home/tmc_ai_common/ALEX/config/company-ca.pem
M365_CA_BUNDLE=/home/tmc_ai_common/ALEX/config/company-ca.pem
```

```bash
chmod 600 .env

# 3) Sửa config.yaml — client_id + tenant_id (IT cấp)
nano config.yaml

# 4) Kiểm tra SSL
./scripts/ubuntu_m365_ssl_check.sh

# 5) Chạy server (giữ terminal mở)
./chay.sh
```

Mở browser: `http://<IP-may>:8765/login` → **admin** / **Alex@2025!**

Tab **Review** → **Sign in to Microsoft 365**

---

## Mỗi ngày

```bash
cd /home/tmc_ai_common/ALEX
./chay.sh
```

Ctrl+C để dừng.

---

## Lỗi thường gặp

| Triệu chứng | Cách sửa |
|-------------|----------|
| Sign in M365 báo **SSL error** | Chưa có `config/company-ca.pem` → nhờ IT. Chạy `./scripts/ubuntu_m365_ssl_check.sh` |
| Thiếu `web/http_ssl.py` | Code lệch — `git pull` full folder, không copy lẻ |
| Đồng nghiệp không vào được web | Sửa IP: `./scripts/set_lan_ip.sh` rồi restart `./chay.sh` |
| Quên pass admin | `source .venv/bin/activate && python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'` |
| Sửa `.env` / config xong mà không đổi | **Restart** `./chay.sh` (server không tự reload) |

---

## Cập nhật phiên bản mới

```bash
cd /home/tmc_ai_common/ALEX
./scripts/ubuntu_backup.sh          # backup web_data + .env
git pull origin main                # hoặc giải nén ZIP mới
source .venv/bin/activate && pip install -r requirements.txt
./scripts/ubuntu_deploy_gates.sh
./chay.sh
```

Chi tiết: [UBUNTU_UPDATE_POLICY.md](./UBUNTU_UPDATE_POLICY.md)
