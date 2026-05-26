# Cài ALEX trên Ubuntu — hướng dẫn ngắn

Chỉ cần nhớ **một folder** trên server (ví dụ bạn đang dùng):

```text
/home/tmc_ai_common/ALEX
```

Mọi lệnh đều chạy **trong folder đó**. Không cần nhớ thêm path dài trong `.env`.

---

## VS Code và Ubuntu — sync thế nào?

```text
  SAI (hay bi lech code):
  Mac: ~/TMC_Cursor/ALEX  --copy tay-->  Ubuntu: /home/.../ALEX
         ^ VS Code mo folder Mac              server chay folder khac

  DUNG (luon dong bo):
  VS Code Remote SSH --> mo thang /home/tmc_ai_common/ALEX tren Ubuntu
                         moi file Save = tren server, khong qua Mac
```

| Bạn đang làm gì | Cách làm |
|-----------------|----------|
| **Chạy server team** | Chỉ sửa file trên Ubuntu (Remote SSH hoặc terminal SSH) |
| **Dev trên Mac** | Folder Mac riêng, `./dev.sh` — **không** tự sync lên server |
| **Đưa code mới lên server** | Trên Ubuntu: `git pull` **hoặc** ZIP cả folder — **không** copy lẻ 1 file |

**Kiểm tra nhanh bạn đang sửa đúng chỗ chưa:**

```bash
pwd
# Phai in: /home/tmc_ai_common/ALEX (hoac folder ALEX tren server)

ls web/http_ssl.py
# Phai thay file — neu "No such file" = code lech, can git pull full
```

---

## Nhờ IT — tối thiểu

| Bắt buộc (M365) | Tuỳ chọn (chỉ khi lỗi SSL) |
|-----------------|----------------------------|
| `client_id`, `tenant_id`, secret **Value** | 1 file root CA (`.pem`) |
| Allow public client flows (Azure) | |
| Port **8765** mở trong LAN | |

**Thử không xin CA trước:** sau `./setup_ubuntu.sh`, chạy `./scripts/ubuntu_m365_ssl_check.sh`.  
- In **OK** → không cần file CA, không cần IT thêm gì cho SSL.  
- In **FAIL** (certificate error) → nhờ IT 1 file `.pem`, đặt tên `config/company-ca.pem` — xong.

---

## `REQUESTS_CA_BUNDLE` / `M365_CA_BUNDLE` là gì?

Hai dòng đó **chỉ** báo cho Python: “file chứng chỉ công ty nằm ở đâu”.

- **Không bắt buộc** nếu bạn đặt file tại: **`config/company-ca.pem`** (ALEX tự tìm).
- Chỉ thêm vào `.env` khi file CA nằm chỗ khác (ví dụ `/etc/ssl/corp.pem`).

`.env` tối thiểu thường chỉ cần **một dòng**:

```
M365_CLIENT_SECRET=<Value tu Azure>
```

---

## Cài lần đầu — 3 bước

### 1. Lấy code (full folder)

```bash
cd /home/tmc_ai_common/ALEX
git pull origin main
```

### 2. Cài

```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

### 3. Điền secret, thử SSL, chạy

```bash
nano .env          # chi M365_CLIENT_SECRET=
nano config.yaml   # client_id + tenant_id (IT cap)

./scripts/ubuntu_m365_ssl_check.sh
# FAIL + loi SSL → cp file IT vao config/company-ca.pem roi chay lai script

./chay.sh
```

Browser: `http://<IP-may>:8765/login` → admin / Alex@2025!

---

## Mỗi ngày

```bash
cd /home/tmc_ai_common/ALEX
./chay.sh
```

Sửa `.env` hoặc config → **Ctrl+C** rồi `./chay.sh` lại.

---

## Lỗi thường gặp

| Triệu chứng | Cách sửa |
|-------------|----------|
| Code Mac khác Ubuntu | Dung VS Code Remote SSH vao server; `git pull` tren server |
| SSL khi Sign in M365 | `./scripts/ubuntu_m365_ssl_check.sh` → neu FAIL thi `config/company-ca.pem` |
| Sua file ma app khong doi | Restart `./chay.sh` |

Gửi IT (khi can): [IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md)
