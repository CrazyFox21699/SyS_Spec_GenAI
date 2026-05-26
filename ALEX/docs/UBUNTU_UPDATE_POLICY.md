# Chính sách cập nhật ALEX trên Ubuntu công ty

Tránh lệch code (thiếu file, SSL lỗi) do copy lẻ từ GitHub.

---

## Nguyên tắc

| Làm | Không làm |
|-----|-----------|
| Một thư mục cố định: `/home/tmc_ai_common/ALEX` | Copy 2–3 file từ GitHub UI vào VS Code |
| Cập nhật **full release** (ZIP hoặc `git checkout <tag>`) | Sửa Python trực tiếp trên server production |
| Chỉ sửa **config runtime**: `config.yaml`, `.env`, `config/company-ca.pem` | `M365_SSL_VERIFY=false` (vi phạm ISMS) |
| Chạy **deploy gates** sau mỗi cập nhật | Bỏ qua verify, test Sign in ngay |

---

## VS Code — một nguồn sự thật

1. Cài extension **Remote - SSH**
2. SSH vào máy Ubuntu công ty
3. **File → Open Folder** → `/home/tmc_ai_common/ALEX`
4. Mọi chỉnh sửa config/.env trên **path này** — không edit bản copy trên Mac rồi paste thủ công

Nếu mở folder ALEX trên Mac local: chỉ dùng để dev (`./dev.sh`), **không** sync thủ công lên server.

---

## Cập nhật phiên bản (hàng tháng / quý)

### Bước 1 — Backup

```bash
cd /home/tmc_ai_common/ALEX
./scripts/ubuntu_backup.sh
```

Giữ file `alex-backup-YYYYMMDD-HHMMSS.tgz` (chứa `web_data/`, `.env`, `config.yaml`, CA).

### Bước 2 — Deploy full release

**ZIP:**

1. Trên máy dev: `python scripts/sanitize_for_company_deploy.py` → zip folder `ALEX/`
2. Copy ZIP sang Ubuntu
3. Giải nén **đè** code (giữ backup)
4. Khôi phục runtime từ backup:
   ```bash
   cd /home/tmc_ai_common
   tar xzf alex-backup-YYYYMMDD.tgz
   ```

**Git (nếu có clone):**

```bash
cd /home/tmc_ai_common/ALEX
git fetch
git checkout <tag-release>
git status   # phải có web/http_ssl.py
```

### Bước 3 — Dependencies

```bash
cd /home/tmc_ai_common/ALEX
source .venv/bin/activate
pip install -r requirements.txt
```

### Bước 4 — Deploy gates (bắt buộc)

```bash
chmod +x cai_dat.sh chay.sh scripts/*.sh
./scripts/ubuntu_deploy_gates.sh
```

Phải pass:

1. `ubuntu_release_sync_check.sh` — đủ file M365/SSL
2. `ubuntu_preflight.sh`
3. `ubuntu_m365_ssl_check.sh` — Microsoft HTTPS OK với company CA
4. (Khi `./chay.sh` chạy) `ubuntu_verify.sh` + `/api/m365/connectivity`

### Bước 5 — Restart

```bash
# Ctrl+C terminal cũ nếu đang chạy
./chay.sh
```

Browser: **Ctrl+Shift+R** → Sign in M365.

---

## Cài lần đầu

Xem [HUONG_DAN_CAI_DAT_UBUNTU.md](./HUONG_DAN_CAI_DAT_UBUNTU.md) và gửi IT [IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md).

---

## Khi SSL vẫn lỗi

1. Có `config/company-ca.pem` từ IT chưa?
2. `.env` có `REQUESTS_CA_BUNDLE` đúng path?
3. `config.yaml` có `assist.m365.ssl_verify: true`?
4. `ls web/http_ssl.py` — nếu thiếu → redeploy full release, không patch lẻ
5. `curl -v https://login.microsoftonline.com` trên server — nếu fail → IT/network

---

## Script tham chiếu

| Script | Khi nào chạy |
|--------|----------------|
| `scripts/ubuntu_release_sync_check.sh` | Sau deploy / trước chạy server |
| `scripts/ubuntu_preflight.sh` | Trước `./cai_dat.sh` lần đầu |
| `scripts/ubuntu_m365_ssl_check.sh` | Trước Sign in M365 |
| `scripts/ubuntu_verify.sh` | Khi `./chay.sh` đang chạy |
| `scripts/ubuntu_deploy_gates.sh` | Gom tất cả gates trên |
| `scripts/ubuntu_backup.sh` | Trước mỗi lần nâng cấp |
