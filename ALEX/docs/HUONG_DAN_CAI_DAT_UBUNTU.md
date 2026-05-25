# Hướng dẫn cài ALEX trên Ubuntu (LAN team)

Tài liệu chi tiết + xử lý lỗi thường gặp. Tóm tắt nhanh vẫn nằm ở [README.md](../README.md).

---

## Checklist trước khi cài

| # | Việc cần làm | Lệnh / ghi chú |
|---|--------------|----------------|
| 1 | Ubuntu 20.04+ với Python 3.9+ | `python3 --version` |
| 2 | Mở port **8765** (firewall) | `sudo ufw allow 8765/tcp` |
| 3 | Biết **IP LAN** máy server | `hostname -I` |
| 4 | Sửa `config.yaml` → `deployment.lan_ipv4` + `public_url` | Khớp IP thật |
| 5 | IT cấp **client_id**, **tenant_id**, **secret Value** | Secret vào `.env`, không ghi yaml |
| 6 | IT bật **Allow public client flows** | Azure → Authentication |
| 7 | User có license **M365 Copilot** (nếu dùng AI) | Không bắt buộc cho review offline |

---

## Cài lần đầu (3 lệnh)

```bash
cd /path/to/ALEX
chmod +x cai_dat.sh chay.sh scripts/ubuntu_preflight.sh scripts/ubuntu_verify.sh
./scripts/ubuntu_preflight.sh    # kiểm tra môi trường (không sửa gì)
./cai_dat.sh                     # venv + pip + admin user
cp .env.example .env && chmod 600 .env   # nếu chưa có — dán M365_CLIENT_SECRET
./chay.sh                         # worker + web (giữ terminal mở)
```

Mở browser: `http://<IP-LAN>:8765/login` — `admin` / `Alex@2025!`

Sau khi server chạy, terminal khác:

```bash
./scripts/ubuntu_verify.sh
```

---

## Cấu hình bắt buộc trên Ubuntu

### 1. IP và URL (`config.yaml`)

```yaml
deployment:
  mode: production      # bật worker nền — KHÔNG đổi thành local trên server team
  host: 0.0.0.0         # lắng nghe mọi interface
  port: 8765
  lan_ipv4: 192.168.x.x    # IP thật của máy (hostname -I)
  public_url: http://192.168.x.x:8765
```

**Lỗi thường gặp:** copy nguyên `10.88.152.11` từ repo mẫu → đồng nghiệp không vào được. Phải sửa đúng IP máy bạn.

### 2. File `.env` (secret)

```bash
M365_CLIENT_SECRET=<paste Value từ Azure, KHÔNG phải Secret ID>
# Tuỳ chọn nếu không muốn sửa config.yaml:
# M365_CLIENT_ID=...
# M365_TENANT_ID=...
```

```bash
chmod 600 .env
```

### 3. `assist` + `features` (M365-only)

Giữ đồng bộ với repo:

```yaml
features:
  ollama_assist: false
llm:
  enabled: false
assist:
  default_provider: m365
  allow_ollama_fallback: false
  m365:
    enabled: true
    client_id: "..."
    tenant_id: "..."
    client_secret: ""
  copilot:
    enabled: false
```

**Ollama Unavailable** trên UI là **bình thường** — ALEX không cần Ollama khi dùng M365 Copilot.

---

## Chạy hàng ngày

```bash
cd /path/to/ALEX
./chay.sh
```

- **Một terminal** — Ctrl+C dừng web + worker.
- Log worker: `/tmp/alex-worker.log`
- Không cần `python -m uvicorn ...` thủ công trừ khi debug.

### Chạy nền với systemd (tuỳ chọn)

Copy mẫu [deploy/alex.service.example](../deploy/alex.service.example), sửa `WorkingDirectory` và `User`, rồi:

```bash
sudo cp deploy/alex.service.example /etc/systemd/system/alex.service
# sửa file service: đường dẫn ALEX + User
sudo systemctl daemon-reload
sudo systemctl enable --now alex
journalctl -u alex -f
```

---

## Xử lý lỗi thường gặp

### Không mở được trang từ máy khác trong LAN

1. Server có chạy `./chay.sh` không? `ss -tlnp | grep 8765`
2. `deployment.host` có phải `0.0.0.0`?
3. Firewall: `sudo ufw status` — port 8765 ALLOW
4. Ping IP server từ máy client
5. Thử `curl http://127.0.0.1:8765/` trên chính server

### Login admin không được

```bash
source .venv/bin/activate
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'
```

Restart `./chay.sh`.

### M365: "Sign in required" / Copilot nút disabled

1. `.env` có `M365_CLIENT_SECRET` (Value đúng)?
2. `config.yaml`: `client_id`, `tenant_id` đúng app IT tạo?
3. IT bật **Allow public client flows**
4. User sign in bằng **work account** (không phải Microsoft cá nhân)
5. Account có license **Microsoft 365 Copilot** — không có thì vẫn dùng **Apply locally** + **Regenerate** Test Code

### M365 login OK nhưng Copilot Chat fail

- Kiểm tra SKU Copilot trên account
- Xem banner trên tab Review / Logic (MSA vs no license)
- Chi tiết: [M365_COPILOT_ACTIVATION_GUIDE.md](./M365_COPILOT_ACTIVATION_GUIDE.md)

### Review job / Test Code báo "Not Found" / API cũ

- Hard refresh browser: **Cmd/Ctrl + Shift + R**
- Restart `./chay.sh` sau khi cập nhật code
- Kiểm tra `app.js?v=` trong `index.html` đã mới

### `pip` / venv lỗi khi `./cai_dat.sh`

```bash
sudo apt install -y python3-venv python3-pip
rm -rf .venv
./cai_dat.sh
```

Cảnh báo `cache entry deserialization failed` — bỏ qua nếu cài vẫn xong.

### Phân tích spec treo / không xong

- Xem `/tmp/alex-worker.log`
- `deployment.mode` phải là `production` trên Ubuntu team
- Upload lại và bấm Review trên tab Spec review

### Quyền ghi `web_data/`

```bash
mkdir -p web_data/uploads web_data/output
chmod -R u+rwX web_data
```

User chạy `./chay.sh` phải sở hữu thư mục ALEX.

### Folder `.alex` / dữ liệu runtime

ALEX lưu cấu hình GTest + project memory trong **`ALEX/web_data/.alex/`** (không tạo `.alex` trong folder spec bên ngoài).

```bash
ls -la web_data/.alex/
# gtest_harness_preset.yaml, project_memory.yaml, code_style_samples.yaml
```

Backup trước khi cập nhật: `tar czf alex-web_data-backup.tgz web_data/ .env`

Nếu nâng cấp từ bản cũ trỏ `pm_test_spec_assistant`: khởi động server một lần — app tự migrate sang `web_data/.alex/`.

---

## Cập nhật phiên bản mới

1. Backup `web_data/` và `.env`
2. Giải nén ZIP mới vào thư mục ALEX (hoặc merge)
3. `source .venv/bin/activate && pip install -r requirements.txt`
4. Giữ lại `.env` và `config.yaml` đã sửa IP
5. `./chay.sh`

Trước khi zip gửi đi: `python scripts/sanitize_for_company_deploy.py`

---

## Liên hệ IT — checklist một trang

Gửi IT khi cần bật Copilot:

- [ ] App registration: client_id + tenant_id
- [ ] Client secret **Value** → engineer đặt trong `.env`
- [ ] Delegated: openid, profile, email, offline_access, User.Read + admin consent
- [ ] Authentication → **Allow public client flows: Yes**
- [ ] User test có license **Microsoft 365 Copilot**
- [ ] Firewall nội bộ cho phép LAN → port **8765** TCP
