# Cài ALEX trên Ubuntu công ty

**Không cần `git clone`.** Tải ZIP từ GitHub → giải nén → 2 lệnh setup.

---

## Bước 1 — Tải mã nguồn (trên máy có internet)

1. Mở: https://github.com/CrazyFox21699/SyS_Spec_GenAI  
2. Bấm nút **Code** → **Download ZIP**  
3. Được file `SyS_Spec_GenAI-main.zip`

Chuyển file ZIP sang máy Ubuntu công ty (USB, email nội bộ, shared drive…).

---

## Bước 2 — Giải nén trên Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip

cd ~
unzip SyS_Spec_GenAI-main.zip
cd SyS_Spec_GenAI-main/pm_test_spec_assistant
```

*(Nếu tên folder khác, ví dụ `SyS_Spec_GenAI-master`, `cd` vào folder tương ứng rồi vào `pm_test_spec_assistant`)*

**Gợi ý:** đổi tên cho dễ nhớ (tuỳ chọn):

```bash
mv ~/SyS_Spec_GenAI-main ~/ALEX
cd ~/ALEX/pm_test_spec_assistant
```

---

## Bước 3 — Cài ALEX (1 lần)

```bash
chmod +x cai_dat.sh chay.sh
./cai_dat.sh
sudo ufw allow 8765/tcp
```

Đợi đến khi thấy **Xong**.

---

## Bước 4 — Chạy server (mỗi ngày)

```bash
cd ~/ALEX/pm_test_spec_assistant
# hoặc: cd ~/SyS_Spec_GenAI-main/pm_test_spec_assistant

./chay.sh
```

Giữ **Terminal mở**. `Ctrl+C` để dừng.

---

## Đăng nhập

| | |
|---|---|
| Link | http://10.88.152.11:8765/login |
| User | `admin` |
| Pass | `Alex@2025!` *(có dấu `!` cuối)* |

Đồng nghiệp Windows/LAN: cùng link — **không cài gì**, chỉ mở browser.  
Admin tạo user mới: http://10.88.152.11:8765/admin

---

## Quên mật khẩu admin

```bash
cd ~/ALEX/pm_test_spec_assistant
source .venv/bin/activate
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'
```

---

## IP máy khác 10.88.152.11?

Sửa trong `config.yaml`:

```yaml
deployment:
  lan_ipv4: <IP-may-ban>
  public_url: http://<IP-may-ban>:8765
```

Rồi chạy lại `./chay.sh`.

---

## Cập nhật phiên bản mới (tải ZIP lại)

1. Tải ZIP mới từ GitHub (bước 1)  
2. Giải nén đè hoặc vào folder mới  
3. **Giữ lại** folder `web_data/` cũ (upload + job) nếu cần  
4. Chạy lại `./cai_dat.sh` nếu cài folder mới hoàn toàn  

---

## Tóm tắt nhanh

```text
Download ZIP → unzip → cd pm_test_spec_assistant → ./cai_dat.sh → ./chay.sh
Login: http://10.88.152.11:8765/login  ·  admin / Alex@2025!
```
