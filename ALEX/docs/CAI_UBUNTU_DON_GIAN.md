# Hướng dẫn cài ALEX trên Ubuntu (đầy đủ)

Tài liệu **duy nhất** cần đọc khi cài server LAN. Mac dev dùng `./dev.sh` — **không** dùng file này.

**Repo GitHub:** https://github.com/CrazyFox21699/SyS_Spec_GenAI  
**Folder chạy app:** `SyS_Spec_GenAI/ALEX/` (hoặc copy/symlink thành `/home/tmc_ai_common/ALEX`)

---

## Tóm tắt 1 trang

| Bước | Lệnh |
|------|------|
| 1. Lấy code | `git clone …` hoặc `git pull` (xem mục 2) |
| 2. Cài | `cd ALEX && ./setup_ubuntu.sh` |
| 3. Secret M365 | `nano .env` → `M365_CLIENT_SECRET=…` |
| 4. ID Azure | `nano config.yaml` → `client_id`, `tenant_id` |
| 5. Kiểm tra SSL | `./scripts/ubuntu_m365_ssl_check.sh` |
| 6. Chạy | `./chay.sh` |
| 7. Browser | `http://<IP>:8765/login` → admin / Alex@2025! |

**Mỗi ngày:** `cd ALEX && ./chay.sh`  
**Sửa `.env`/config xong:** Ctrl+C → `./chay.sh` lại (server không tự reload)

---

## 1. Chuẩn bị

### Máy Ubuntu

- Ubuntu 20.04+ · Python 3.9+
- Biết IP LAN: `hostname -I`

### Nhờ IT (M365 — bắt buộc nếu dùng Sign in)

| IT cấp | Bạn làm |
|--------|---------|
| `client_id`, `tenant_id` | Ghi vào `config.yaml` |
| Secret **Value** (Azure) | Ghi vào `.env` |
| Bật **Allow public client flows** | Azure → Authentication |
| Mở port **8765** TCP (LAN → server) | `sudo ufw allow 8765/tcp` |

Mẫu gửi IT: [IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md)

### SSL / file CA (tuỳ chọn — chỉ khi bước 5 FAIL)

Không cần xin IT trước. Chạy `./scripts/ubuntu_m365_ssl_check.sh` sau khi cài:

- **OK** → bỏ qua file CA
- **FAIL** (certificate error) → IT gửi 1 file `.pem` → đặt tên **`config/company-ca.pem`**

Không cần `REQUESTS_CA_BUNDLE` trong `.env` nếu file nằm đúng `config/company-ca.pem`.

---

## 2. Lấy code lên Ubuntu

**Quy tắc:** Luôn lấy **cả folder ALEX** (`git clone` / `git pull` / ZIP). **Không** copy lẻ 1–2 file từ GitHub.

### Lần đầu — Git (khuyến nghị)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip curl ca-certificates unzip

mkdir -p /home/tmc_ai_common
cd /home/tmc_ai_common
git clone https://github.com/CrazyFox21699/SyS_Spec_GenAI.git
cd SyS_Spec_GenAI/ALEX
```

*(Tuỳ chọn: `ln -s …/SyS_Spec_GenAI/ALEX /home/tmc_ai_common/ALEX` để path ngắn hơn)*

### Lần đầu — ZIP (không có git)

1. GitHub → **Code** → **Download ZIP**
2. Copy ZIP sang Ubuntu, giải nén:
   ```bash
   cd /home/tmc_ai_common
   unzip SyS_Spec_GenAI-main.zip
   cd SyS_Spec_GenAI-main/ALEX
   ```

### Đã cài rồi — cập nhật code

```bash
cd /path/to/SyS_Spec_GenAI   # thư mục có .git
git pull origin main
cd ALEX
```

---

## 3. Cài ALEX (một lệnh)

```bash
cd /path/to/ALEX          # phải thấy file setup_ubuntu.sh
chmod +x setup_ubuntu.sh chay.sh scripts/*.sh
./setup_ubuntu.sh
```

Script tự làm:

- Cài gói Ubuntu (python3, venv, ca-certificates…)
- Sửa **IP LAN** trong `config.yaml`
- Tạo `.venv`, cài pip, user `admin`
- Kiểm tra đủ file (`web/http_ssl.py`, …)

Đợi in **`CAI DAT XONG`**.

---

## 4. Cấu hình sau cài

### 4.1 File `.env`

```bash
nano .env
chmod 600 .env
```

Tối thiểu:

```bash
M365_CLIENT_SECRET=paste-Value-tu-Azure-o-day
```

### 4.2 File `config.yaml`

```bash
nano config.yaml
```

Điền (IT cấp):

```yaml
assist:
  m365:
    client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    tenant_id: "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
    ssl_verify: true
```

IP LAN đã được `./setup_ubuntu.sh` sửa; kiểm tra:

```yaml
deployment:
  mode: production
  host: 0.0.0.0
  port: 8765
  lan_ipv4: <IP-that>
  public_url: http://<IP-that>:8765
```

### 4.3 SSL (chỉ nếu cần)

```bash
./scripts/ubuntu_m365_ssl_check.sh
```

Nếu FAIL → `cp /path/from/it/root.pem config/company-ca.pem` → chạy lại script.

---

## 5. Chạy server

```bash
./chay.sh
```

Giữ terminal mở. Ctrl+C dừng web + worker.

Terminal khác (tuỳ chọn):

```bash
./scripts/ubuntu_verify.sh
curl -s http://127.0.0.1:8765/api/m365/connectivity | python3 -m json.tool
```

Kỳ vọng: `"ok": true`

### Đăng nhập

| | |
|---|---|
| URL | `http://<IP-LAN>:8765/login` |
| User / pass | `admin` / `Alex@2025!` |
| M365 | Tab **Review** → Sign in (work account) |

Không có license Copilot vẫn review spec + export Excel offline.

---

## 6. VS Code — đồng bộ với Ubuntu

**Vấn đề thường gặp:** Sửa code trên Mac → server Ubuntu không đổi.

**Cách đúng:** VS Code **Remote SSH** mở thẳng folder ALEX trên server.

1. Cài extension **Remote - SSH**
2. `Cmd/Ctrl+Shift+P` → **Remote-SSH: Connect to Host** → chọn máy Ubuntu
3. **File → Open Folder** → `/home/tmc_ai_common/SyS_Spec_GenAI/ALEX` (hoặc path ALEX của bạn)
4. Mọi **Save** = trên server

**Cập nhật code từ GitHub (trên server):**

```bash
cd /path/to/SyS_Spec_GenAI
git pull origin main
cd ALEX
source .venv/bin/activate && pip install -r requirements.txt
./chay.sh
```

**Kiểm tra đang ở đúng folder:**

```bash
pwd && ls web/http_ssl.py setup_ubuntu.sh
```

---

## 7. Vận hành hàng ngày

```bash
cd /path/to/ALEX
./chay.sh
```

| Việc | Lệnh |
|------|------|
| Log worker | `tail -f /tmp/alex-worker.log` |
| Sửa IP | `./scripts/set_lan_ip.sh` → restart `./chay.sh` |
| Quên pass admin | `source .venv/bin/activate && python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'` |
| Backup trước nâng cấp | `./scripts/ubuntu_backup.sh` |
| Kiểm tra trước Sign in M365 | `./scripts/ubuntu_deploy_gates.sh` |

---

## 8. Cập nhật phiên bản mới

```bash
cd /path/to/ALEX
./scripts/ubuntu_backup.sh
cd .. && git pull origin main && cd ALEX
source .venv/bin/activate && pip install -r requirements.txt
./scripts/ubuntu_deploy_gates.sh
./chay.sh
```

Chi tiết: [UBUNTU_UPDATE_POLICY.md](./UBUNTU_UPDATE_POLICY.md)

---

## 9. Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách sửa |
|-------------|-------------|----------|
| Thiếu `web/http_ssl.py` | Copy lẻ file | `git pull` full repo |
| Sign in M365 SSL error | Proxy công ty | `config/company-ca.pem` + chạy lại ssl check |
| Sửa file không có hiệu lực | Chưa restart | Ctrl+C → `./chay.sh` |
| Đồng nghiệp không vào web | Sai IP / firewall | `./scripts/set_lan_ip.sh`, mở port 8765 |
| Mac vs Ubuntu khác code | Sửa nhầm folder Mac | VS Code Remote SSH vào server |
| Ollama Unavailable trên UI | Bình thường | ALEX dùng M365, không cần Ollama |

---

## 10. Script tham chiếu

| Script | Khi nào |
|--------|---------|
| `setup_ubuntu.sh` | Cài lần đầu |
| `chay.sh` | Chạy mỗi ngày |
| `scripts/set_lan_ip.sh` | Đổi IP LAN |
| `scripts/ubuntu_m365_ssl_check.sh` | Trước Sign in M365 |
| `scripts/ubuntu_deploy_gates.sh` | Kiểm tra đủ trước go-live |
| `scripts/ubuntu_verify.sh` | Server đang chạy? |
| `scripts/ubuntu_backup.sh` | Trước nâng cấp |

Xử lý lỗi nâng cao: [HUONG_DAN_CAI_DAT_UBUNTU.md](./HUONG_DAN_CAI_DAT_UBUNTU.md)  
Copilot: [M365_COPILOT_ACTIVATION_GUIDE.md](./M365_COPILOT_ACTIVATION_GUIDE.md)
