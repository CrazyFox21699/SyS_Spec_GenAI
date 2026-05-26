# Yêu cầu IT — ALEX trên Ubuntu server (LAN team)

Gửi email/ticket cho IT. Copy nội dung bên dưới.

---

**Subject:** ALEX internal tool — M365 app + corporate root CA + firewall

**Mục đích:** Tool phân tích test spec nội bộ chạy trên Ubuntu LAN (`/home/tmc_ai_common/ALEX`, port **8765**). Cần đăng nhập Microsoft 365 (device flow) qua HTTPS outbound.

---

## 1. Root CA công ty (bắt buộc cho ISMS — không tắt SSL verify)

Server Ubuntu outbound HTTPS đi qua proxy công ty (SSL inspection). Python cần tin root CA nội bộ.

**Yêu cầu:**

- [ ] File **root CA** định dạng PEM (`.pem` hoặc `.crt`)
- Engineer đặt tại: `/home/tmc_ai_common/ALEX/config/company-ca.pem`
- Hoặc chỉ đường trong `.env`:
  ```
  REQUESTS_CA_BUNDLE=/home/tmc_ai_common/ALEX/config/company-ca.pem
  M365_CA_BUNDLE=/home/tmc_ai_common/ALEX/config/company-ca.pem
  ```

**Giải thích ngắn:** Trình duyệt trên máy Windows/Mac đã cài CA công ty nên web Microsoft mở bình thường. Ubuntu server + Python **không** tự có CA đó — cần file PEM từ IT.

**Không yêu cầu:** Tắt SSL verify (`M365_SSL_VERIFY=false`) — vi phạm ISMS.

---

## 2. Azure App Registration (M365 Sign-in)

- [ ] **client_id** (Application ID)
- [ ] **tenant_id** (Directory ID)
- [ ] Client secret **Value** (không phải Secret ID) — engineer đặt trong `.env` trên server

**Azure cấu hình:**

- [ ] Authentication → **Allow public client flows: Yes**
- [ ] API permissions (Delegated): `openid`, `profile`, `email`, `offline_access`, `User.Read`
- [ ] **Admin consent** cho các permission trên

---

## 3. Mạng / firewall

**Inbound (LAN → server):**

- [ ] Cho phép TCP **8765** từ mạng LAN nội bộ tới máy Ubuntu host ALEX

**Outbound (server → Internet):**

- [ ] HTTPS tới `login.microsoftonline.com`
- [ ] HTTPS tới `graph.microsoft.com`

---

## 4. License (tuỳ chọn — cho Copilot AI)

- [ ] User test có license **Microsoft 365 Copilot** (work account)

Không có license: vẫn review spec + export Excel offline; chỉ các nút Copilot AI bị tắt.

---

## Kiểm tra sau khi IT cung cấp CA

Engineer chạy trên server:

```bash
cd /home/tmc_ai_common/ALEX
cp /path/from/it/root-ca.pem config/company-ca.pem
chmod 644 config/company-ca.pem
# thêm REQUESTS_CA_BUNDLE vào .env nếu cần
./scripts/ubuntu_deploy_gates.sh
./chay.sh
```

Khi `./scripts/ubuntu_m365_ssl_check.sh` in **OK** → Sign in M365 trên tab Review.
