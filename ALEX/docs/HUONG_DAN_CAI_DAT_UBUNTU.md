# Hướng dẫn cài ALEX trên Ubuntu (LAN team)

Tài liệu chi tiết + xử lý lỗi thường gặp. Tóm tắt nhanh vẫn nằm ở [README.md](../README.md).

**Triển khai ổn định (ISMS, không patch code lẻ):**

- [UBUNTU_UPDATE_POLICY.md](./UBUNTU_UPDATE_POLICY.md) — chính sách cập nhật full release
- [IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md) — gửi IT (root CA + M365 + firewall)

---

## Checklist trước khi cài

| # | Việc cần làm | Lệnh / ghi chú |
|---|--------------|----------------|
| 1 | Ubuntu 20.04+ với Python 3.9+ | `python3 --version` |
| 2 | Mở port **8765** (firewall) | `sudo ufw allow 8765/tcp` |
| 3 | Biết **IP LAN** máy server | `hostname -I` |
| 4 | Sửa `config.yaml` → `deployment.lan_ipv4` + `public_url` | Khớp IP thật |
| 5 | IT cấp **client_id**, **tenant_id**, secret **Value** | Secret vào `.env`, không ghi yaml |
| 6 | IT bật **Allow public client flows** | Azure → Authentication |
| 7 | IT cấp **root CA** (`.pem`) cho proxy công ty | `config/company-ca.pem` — xem IT checklist |
| 8 | User có license **M365 Copilot** (nếu dùng AI) | Không bắt buộc cho review offline |

---

## VS Code trên server (tránh lệch code)

1. Extension **Remote - SSH** → SSH vào máy Ubuntu
2. Open folder **`/home/tmc_ai_common/ALEX`** (path cố định)
3. **Không** copy lẻ file từ GitHub vào Mac rồi paste — dùng ZIP/git full tree

Chi tiết: [UBUNTU_UPDATE_POLICY.md](./UBUNTU_UPDATE_POLICY.md)

---

## Cài lần đầu

```bash
cd /home/tmc_ai_common/ALEX
chmod +x cai_dat.sh chay.sh scripts/*.sh
./scripts/ubuntu_preflight.sh
./cai_dat.sh
cp .env.example .env && chmod 600 .env   # nếu chưa có
# IT: root CA → config/company-ca.pem + REQUESTS_CA_BUNDLE trong .env
./scripts/ubuntu_deploy_gates.sh
./chay.sh
```

Mở browser: `http://<IP-LAN>:8765/login` — `admin` / `Alex@2025!`

---

## Cấu hình bắt buộc trên Ubuntu

### 1. IP và URL (`config.yaml`)

```yaml
deployment:
  mode: production
  host: 0.0.0.0
  port: 8765
  lan_ipv4: 192.168.x.x
  public_url: http://192.168.x.x:8765
```

### 2. SSL ISMS — company root CA

```bash
mkdir -p config
cp /path/from/it/root-ca.pem config/company-ca.pem
chmod 644 config/company-ca.pem
```

`.env`:

```bash
M365_CLIENT_SECRET=<Value từ Azure>
REQUESTS_CA_BUNDLE=/home/tmc_ai_common/ALEX/config/company-ca.pem
M365_CA_BUNDLE=/home/tmc_ai_common/ALEX/config/company-ca.pem
chmod 600 .env
```

`config.yaml`:

```yaml
assist:
  m365:
    enabled: true
    ssl_verify: true    # ISMS: KHÔNG đặt false
    client_id: "..."
    tenant_id: "..."
    client_secret: ""
```

**Tại sao Mac OK mà Ubuntu lỗi?** Mac dev có thể đã tin CA công ty (Keychain) hoặc không qua proxy SSL inspection. Ubuntu server + Python `requests` cần file CA từ IT.

### 3. `assist` + `features` (M365-only)

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
  copilot:
    enabled: false
```

**Ollama Unavailable** trên UI là **bình thường**.

---

## Chạy hàng ngày

```bash
cd /home/tmc_ai_common/ALEX
./chay.sh
```

- **Một terminal** — Ctrl+C dừng web + worker.
- Log worker: `/tmp/alex-worker.log`
- Sau sửa config/.env: **restart** `./chay.sh` (không auto-reload)

### Deploy gates (trước Sign in M365)

```bash
./scripts/ubuntu_deploy_gates.sh
```

---

## Xử lý lỗi thường gặp

### M365 Sign in: SSL certificate verify failed

```bash
cd /home/tmc_ai_common/ALEX
./scripts/ubuntu_release_sync_check.sh   # đủ web/http_ssl.py?
./scripts/ubuntu_m365_ssl_check.sh       # Microsoft HTTPS OK?
```

1. Có `config/company-ca.pem` từ IT?
2. `.env` có `REQUESTS_CA_BUNDLE` đúng path?
3. `ssl_verify: true` trong config (không dùng `M365_SSL_VERIFY=false`)
4. Thiếu file → redeploy full release, không copy lẻ

### Không mở được trang từ máy khác trong LAN

1. `./chay.sh` đang chạy? `ss -tlnp | grep 8765`
2. `deployment.host: 0.0.0.0`
3. Firewall port 8765

### Login admin không được

```bash
source .venv/bin/activate
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'
```

Restart `./chay.sh`.

### M365: Sign in required

1. `M365_CLIENT_SECRET` trong `.env`
2. `client_id` / `tenant_id` trong config
3. Allow public client flows
4. `./scripts/ubuntu_m365_ssl_check.sh` phải OK trước

Chi tiết Copilot: [M365_COPILOT_ACTIVATION_GUIDE.md](./M365_COPILOT_ACTIVATION_GUIDE.md)

---

## Backup và cập nhật

```bash
./scripts/ubuntu_backup.sh
# deploy full ZIP/git → pip install -r requirements.txt
./scripts/ubuntu_deploy_gates.sh
./chay.sh
```

Trước khi zip gửi công ty: `python scripts/sanitize_for_company_deploy.py`

Chi tiết: [UBUNTU_UPDATE_POLICY.md](./UBUNTU_UPDATE_POLICY.md)

---

## Liên hệ IT

Gửi file [IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md) — root CA, Azure app, firewall, Copilot license.
