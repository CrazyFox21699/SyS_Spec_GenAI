# ALEX — Test Spec Assistant (v0.3)

Công cụ local cho engineer automotive / power-mode: **phân loại** tài liệu khách hàng, **trích xuất** logic điều khiển kèm evidence, **review** và **export** workbook `TestSpec_<Module>_EN.xlsx` / `_JP.xlsx`.

- **Deterministic-first** — cấu trúc AND/OR/NOT từ parser cố định, không phụ thuộc AI.
- **Review-first** — logic mơ hồ → issue + candidate bị chặn, không tự đoán.
- **AI (M365 Copilot only)** — Resolve with Copilot, Improve I/O, Translate workbook qua Microsoft 365 Copilot Chat API (cần license + Sign in). GitHub Copilot CLI **tắt** trên server multi-user.

Hướng dẫn vận hành trong app: tab **Guide** (tiếng Việt).

**Tài liệu thêm:**

| File | Nội dung |
|------|----------|
| [docs/CAI_UBUNTU_DON_GIAN.md](docs/CAI_UBUNTU_DON_GIAN.md) | **Cài Ubuntu — 3 bước (đọc file này trước)** |
| [docs/HUONG_DAN_CAI_DAT_UBUNTU.md](docs/HUONG_DAN_CAI_DAT_UBUNTU.md) | Chi tiết + xử lý lỗi nâng cao |
| [docs/UBUNTU_UPDATE_POLICY.md](docs/UBUNTU_UPDATE_POLICY.md) | Cập nhật full release — không copy lẻ file |
| [docs/IT_REQUEST_CHECKLIST.md](docs/IT_REQUEST_CHECKLIST.md) | Gửi IT: root CA + M365 + firewall |
| [docs/M365_COPILOT_ACTIVATION_GUIDE.md](docs/M365_COPILOT_ACTIVATION_GUIDE.md) | Sign in M365 + license Copilot |
| [config/testcase_style.yaml](config/testcase_style.yaml) | Quy tắc viết testcase cho Copilot |

---

## Cấu trúc repo (sau khi dọn)

Chỉ cần folder **`ALEX/`**:

```text
ALEX/
  cai_dat.sh      # cài lần đầu (Ubuntu)
  chay.sh         # chạy server hàng ngày
  dev.sh          # dev Mac (config.local.yaml)
  config.yaml     # cấu hình LAN / auth / AI (Ubuntu)
  run_web.py      # web UI
  sample_inputs/  # file spec demo + Library canvas mặc định
  web_data/       # runtime: upload, job, session
    .alex/        # harness preset, project memory, code samples (tự tạo)
  src/ web/ tests/ docs/
```

Không cần `power-spec-kit`, `power-mode-spec-pipeline`, hay folder cũ `pm_test_spec_assistant`. Mọi cấu hình runtime (harness GTest, project memory, code style samples) nằm trong **`ALEX/web_data/.alex/`** — không tạo folder `.alex` bên ngoài repo.

---

## Lưu trữ dữ liệu (runtime)

| Thư mục | Nội dung | Ai sửa |
|---------|----------|--------|
| `web_data/uploads/` | File spec upload, job đang chạy | App tự ghi |
| `web_data/output/` | Excel export, bundle phân tích | App tự ghi |
| `web_data/.alex/` | `gtest_harness_preset.yaml`, `project_memory.yaml`, `code_style_samples.yaml` | Bấm **Library** / **Save harness** trên Test Code |
| `sample_inputs/input/` | File spec trên Library canvas (mặc định) | Engineer copy file vào hoặc chọn folder khác trên UI |

**Backup trước khi cập nhật ZIP:** giữ `web_data/` (gồm `.alex/`) và `.env`. Không commit `.env` hay nội dung `.alex/` lên git.

---

## Cài trên Ubuntu server (LAN team)

**Đọc trước:** [docs/CAI_UBUNTU_DON_GIAN.md](docs/CAI_UBUNTU_DON_GIAN.md) — 3 bước, không cần hiểu hết Linux.

```bash
cd /home/tmc_ai_common/ALEX    # hoặc folder ALEX sau khi giải nén ZIP
git pull origin main           # lấy code mới nhất
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh              # cài 1 lần — tự sửa IP, venv, admin
# điền .env + config/company-ca.pem (IT cấp)
./chay.sh                      # chạy mỗi ngày
```

| | |
|---|---|
| Link web | `http://<IP-LAN>:8765/login` |
| Đăng nhập team | `admin` / `Alex@2025!` |
| Sign in M365 | Tab Review (cần CA từ IT + secret trong `.env`) |

Không có M365 vẫn dùng được: upload spec, review logic, export Excel.

<details>
<summary>Chi tiết từng bước (mở rộng)</summary>

### Checklist trước khi bắt đầu

| # | Việc | Ghi chú |
|---|------|---------|
| 1 | Ubuntu 20.04+ | `python3 --version` ≥ 3.9 |
| 2 | Biết IP LAN server | `hostname -I` — dùng sửa `config.yaml` |
| 3 | Mở port **8765** | `sudo ufw allow 8765/tcp` |
| 4 | IT cấp M365 app | `client_id`, `tenant_id`, secret **Value** → `.env` |
| 5 | (Tuỳ chọn AI) | License **Microsoft 365 Copilot** trên work account |

Không có M365 vẫn chạy được: upload spec, review logic, export Excel, **Regenerate** Test Code (Python skeleton).

### Bước 1 — Tải mã nguồn

1. Mở https://github.com/CrazyFox21699/SyS_Spec_GenAI  
2. **Code** → **Download ZIP** → `SyS_Spec_GenAI-main.zip`  
3. Chuyển ZIP sang máy Ubuntu (USB, shared drive, SCP…)

### Bước 2 — Cài gói hệ thống + giải nén

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip curl

cd ~
unzip SyS_Spec_GenAI-main.zip
cd SyS_Spec_GenAI-main/ALEX
```

*(Tuỳ chọn đổi tên: `mv ~/SyS_Spec_GenAI-main ~/alex-repo` rồi `cd ~/alex-repo/ALEX`)*

### Bước 3 — Sửa IP server (quan trọng)

Mở `config.yaml`, sửa cho khớp IP máy Ubuntu (đừng giữ `10.88.152.11` mẫu):

```yaml
deployment:
  mode: production    # bắt buộc trên server team — có worker nền
  host: 0.0.0.0
  port: 8765
  lan_ipv4: 192.168.x.x          # kết quả hostname -I
  public_url: http://192.168.x.x:8765
```

Sai IP → đồng nghiệp không mở được link LAN.

### Bước 4 — Kiểm tra môi trường (khuyến nghị)

```bash
chmod +x cai_dat.sh chay.sh scripts/ubuntu_preflight.sh scripts/ubuntu_verify.sh scripts/ubuntu_release_sync_check.sh scripts/ubuntu_deploy_gates.sh scripts/ubuntu_m365_ssl_check.sh scripts/ubuntu_backup.sh
./scripts/ubuntu_preflight.sh
```

Script chỉ **đọc** — báo OK/WARN/FAIL (Python, port 8765, `.env`, IP mẫu…). Sửa FAIL trước khi cài.

### Bước 5 — Cài ALEX (1 lần duy nhất)

```bash
./cai_dat.sh
```

Script tự: tạo `.venv`, `pip install`, tạo `.env` từ `.env.example`, tạo user `admin`, tạo `web_data/uploads` + `output`.

Sau khi IT gửi secret, mở `.env`:

```bash
chmod 600 .env
nano .env    # dán M365_CLIENT_SECRET=<Value từ Azure, KHÔNG phải Secret ID>
```

Mở firewall (nếu chưa):

```bash
sudo ufw allow 8765/tcp
```

Đợi đến khi thấy **`=== Xong ===`**. Troubleshooting chi tiết: **[docs/HUONG_DAN_CAI_DAT_UBUNTU.md](docs/HUONG_DAN_CAI_DAT_UBUNTU.md)**.

### Bước 6 — Chạy server (mỗi ngày)

**Một terminal duy nhất** — worker chạy nền, web ở foreground. `Ctrl+C` dừng cả hai.

```bash
cd ~/SyS_Spec_GenAI-main/ALEX   # hoặc đường dẫn bạn đã đặt
./chay.sh
```

- Không cần AI để chạy web + phân tích spec.  
- **Resolve with Copilot**, **Improve I/O**, **Generate with Copilot** cần Sign in M365 trên tab Review.  
- Log worker khi job treo: `tail -f /tmp/alex-worker.log`

Terminal **thứ hai** (kiểm tra server sống):

```bash
cd ~/SyS_Spec_GenAI-main/ALEX
./scripts/ubuntu_verify.sh
```

### Bước 7 — Đăng nhập team

| | |
|---|---|
| Link | `http://<IP-LAN>:8765/login` — IP từ `hostname -I` hoặc `deployment.public_url` |
| User | `admin` |
| Pass | `Alex@2025!` *(có dấu `!` cuối)* |

Đồng nghiệp Windows/Mac trên LAN: cùng link — **chỉ mở browser**, không cài Python.  
Tạo user mới: `/admin` (cần quyền admin).

### Chạy nền với systemd (tuỳ chọn)

Xem mẫu [deploy/alex.service.example](deploy/alex.service.example) — sửa `WorkingDirectory`, `User`, `EnvironmentFile` trỏ tới `.env`. Chi tiết trong [docs/HUONG_DAN_CAI_DAT_UBUNTU.md](docs/HUONG_DAN_CAI_DAT_UBUNTU.md).

</details>

---

## Sửa IP server

```bash
cd /home/tmc_ai_common/ALEX
./scripts/set_lan_ip.sh
./chay.sh
```

---

## Quên mật khẩu admin

```bash
cd ~/SyS_Spec_GenAI-main/ALEX
source .venv/bin/activate
python scripts/reset_team_auth.py --yes --username admin --password 'Alex@2025!'
```

---

## Microsoft 365 Copilot (AI)

IT cấu hình **một lần** trong `config.yaml` — user **không nhập** Client ID / Tenant trên UI:

```yaml
assist:
  default_provider: m365
  allow_ollama_fallback: false
  m365:
    enabled: true
    client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"   # Application (client) ID
    tenant_id: "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"   # Directory (tenant) ID
    client_secret: ""   # Để trống — dùng file .env (xem bên dưới)
  copilot:
    enabled: false      # GitHub Copilot CLI — giữ false trên server multi-user
features:
  ollama_assist: false
llm:
  enabled: false       # Ollama không còn dùng trong ALEX
```

Restart server. User chỉ mở Review → **Sign in** bằng work account công ty.

### Bảo mật client secret (khuyến nghị)

**Không** ghi secret vào `config.yaml` / `config.local.yaml` (dễ lộ khi zip, copy, hoặc commit nhầm).

Dùng file **`.env`** cạnh `config.yaml` — đã có trong `.gitignore`:

```bash
cd ALEX
cp .env.example .env
chmod 600 .env          # Ubuntu: chỉ user chạy server đọc được
```

Nội dung `.env`:

```bash
M365_CLIENT_SECRET=paste-secret-value-here
```

ALEX tự đọc `.env` khi chạy `./dev.sh` / `./chay.sh`. Trên Ubuntu với systemd, service file dùng `EnvironmentFile=/opt/alex/ALEX/.env`.

| Cách lưu | An toàn? | Ghi chú |
|----------|----------|---------|
| `.env` (gitignored) | **Có** | Khuyến nghị Mac + Ubuntu |
| Biến môi trường hệ thống | **Có** | `export M365_CLIENT_SECRET=...` trước khi chạy |
| `config.yaml` / `config.local.yaml` | **Không** | Chỉ dùng tạm dev, không zip lên git |
| Secret ID (GUID) | **Không** | Azure không chấp nhận làm secret |

Trước khi zip gửi công ty: chạy `python scripts/sanitize_for_company_deploy.py` — script xóa secret trong yaml nếu có.

### Secret ID vs Secret Value (IT)

Azure Portal → App registration → **Certificates & secrets** → **New client secret** → copy cột **Value** ngay (chỉ hiện một lần).

| IT gửi | Dùng được? |
|--------|------------|
| Application (client) ID | Có — paste vào `client_id` |
| Directory (tenant) ID | Có — paste vào `tenant_id` |
| Secret **ID** (GUID) | **Không** — đây chỉ là mã tham chiếu |
| Secret **Value** (chuỗi dài) | Có — đặt trong `.env` → `M365_CLIENT_SECRET` |

Nếu IT không cung cấp Value: nhờ IT tạo secret mới và gửi Value, **hoặc** bật **Allow public client flows** trên app registration (Authentication) để không cần secret.

**Device sign-in (Review → Sign in):** với app confidential (có secret), IT **cũng cần** bật **Allow public client flows** — Azure → App registration → **Authentication** → Advanced settings → **Allow public client flows: Yes**. Nếu thiếu, Microsoft login trên browser OK nhưng ALEX vẫn báo lỗi token.

### API permissions — Delegated only (theo IT)

IT **không cấp Application permissions** (truy cập cả tenant). ALEX chỉ dùng **Delegated** — mỗi user sign in bằng work account, token gắn với user đó.

**Permissions IT đã grant (đủ cho Sign in + User profile):**

| Permission | Type | Mục đích |
|------------|------|----------|
| `openid` | Delegated | Sign-in |
| `profile` | Delegated | Tên user trên UI |
| `email` | Delegated | Email work account |
| `offline_access` | Delegated | Refresh token |
| `User.Read` | Delegated | Graph `/me`, license check |

Admin consent: **Granted for FPT Corporation** (như screenshot IT gửi).

ALEX map trong `config.yaml`:

```yaml
assist:
  m365:
    login_scopes:
      - openid
      - profile
      - email
      - offline_access
      - User.Read
    copilot_scopes: []   # thêm sau nếu IT grant thêm delegated scopes cho Copilot
```

**Không cần** Mail.Read, Sites.Read.All, … trừ khi IT đồng ý grant thêm (type **Delegated**) và thêm vào `copilot_scopes`.

**Resolve with Copilot (M365 Copilot Chat):** cần user có license **Microsoft 365 Copilot** trên work account. Graph Copilot API dùng **delegated user token** — không dùng Application permission.

**Knowledge workbench (Logic tab):** 4-step Copilot session — **Build context** → **Generate plan** → **Write test cases** → **Review & Apply**. ALEX builds structured Context Pack (logic, paths, gaps, testcase snapshots); Copilot plans then writes full workbook rows per [`config/testcase_style.yaml`](ALEX/config/testcase_style.yaml) + optional golden style samples. Screenshots attach via Logic tab (OCR text included in context).

Legacy **Resolve with Copilot** (Given-only patches) is superseded by this workflow.

Checklist IT (app `FSO.FA.DF.AVE - ALEX_TMC_AI`):

1. API permissions: 5 delegated scopes trên + admin consent ✅  
2. Authentication → **Allow public client flows: Yes** ⬜ (cần bật cho device sign-in)  
3. Client secret Value → `.env` trên server (`M365_CLIENT_SECRET`)  
4. **Không** thêm Application permissions trừ khi IT chính sách thay đổi

ALEX gọi Graph Copilot Chat API khi engineer có SKU **`Microsoft 365 Copilot`** (add-on trả phí).

- Tài khoản Microsoft cá nhân (MSA) hoặc work account **không có license Copilot** → chỉ **Apply locally**; nút Copilot disabled + banner hướng dẫn Sign in / license.
- Chi tiết thao tác: tab **Guide** trong app.

### Testcase editor & Copilot codegen (v0.3+)

Tóm tắt kỹ thuật — **hướng dẫn bấm nút chi tiết** ở các mục [Workflow engineer](#workflow-engineer-thứ-tự-hiệu-quả), [Tab Logic](#tab-logic--copilot-testcase-session), [Tab Test Code](#tab-test-code) bên dưới.

| Tính năng | Mô tả ngắn |
|-----------|------------|
| **Test case editor** | Sửa ID, Function, Event, I/O trên Logic/Export; badge **Engineer** = không bị pipeline ghi đè |
| **Copilot testcase session** | 4 bước: Build context → Plan → Write → Apply — viết full row testcase theo style công ty |
| **Test Code hybrid** | **Regenerate** (offline, nhanh) + **Generate with Copilot** (M365, chất lượng cao) |
| **Code style samples** | Upload 1–3 file `.cpp` mẫu — Copilot bám fixture/helper/comment style |
| **Batch Copilot (Test Code)** | Sinh code cho nhiều TC cùng logic group (mặc định 3 TC/lượt) |
| **Project memory** | Nhớ map I/O → biến C++, verification patterns — dùng lại job/module sau |
| **Centralized `.alex`** | Harness + memory + samples lưu `web_data/.alex/` — portable khi backup `web_data/` |

---

## Workflow engineer (thứ tự hiệu quả)

```text
1. Review        Upload spec → Review specification → đợi job xong
2. Logic         Duyệt logic tree, Definitions, (tuỳ chọn) Verification patterns → Promote
3. Copilot       Build context → Generate plan → Save plan → Write → Apply selected
4. Export        Sửa testcase (ID, I/O) → Save row → Export Excel
5. Test Code     Upload code sample → Generate / Batch Copilot → Save → .cpp
```

**M365 chưa sign in:** bước 3 dùng **Apply locally**; bước 5 chỉ **Regenerate** (Python skeleton). **Ollama Unavailable** trên header — bình thường, không cần cài Ollama.

### Hiệu quả từng chế độ (khi nào dùng gì)

| Bước | Offline (không M365) | Với M365 Copilot | Ghi chú hiệu quả |
|------|----------------------|------------------|------------------|
| Review spec | ✅ Parser + evidence | — | Nhanh, deterministic |
| Logic tree | ✅ Duyệt + Promote patterns | — | Không cần AI |
| Sửa Given nhanh | ✅ **Apply locally** | — | Vài giây, 1–2 signal |
| Viết testcase mới | ⚠️ Chỉ sửa tay / export cũ | ✅ **Write test cases** | Copilot viết full row theo lô (6 TC/lần), retry NO-OP |
| Polish I/O 1 dòng | — | ✅ **Improve I/O** | Khi draft gần đúng |
| Test Code skeleton | ✅ **Regenerate** | — | Vài giây, assert cơ bản |
| Test Code production | — | ✅ **Generate with Copilot** + code sample | Bám style `.cpp` thật; cần I/O đã save |
| Nhiều TC cùng group | Regenerate từng cái | ✅ **Batch Copilot** | 3 TC/lượt (config); review bảng Batch results |

**Mẹo chất lượng Copilot:** (1) Save row I/O trước khi Generate code, (2) attach 1–2 file `.cpp` mẫu, (3) chọn **Reference test**, (4) **Library** một lần per module để lần sau không setup lại harness.

---

## Tab Logic — Copilot testcase session

Panel **Copilot testcase session** (dưới Definitions). Stepper 4 bước: Context → Plan → Write → Review.

| Nút | Khi nào bấm | Hiệu quả |
|-----|-------------|----------|
| **Apply locally** | Engineer gõ constraint đơn giản trong ô note (`SIG=1`, `SIG >= 1`, range…) | Python parse + gán Given — **không cần M365**. Dùng sửa nhanh 1–2 signal trước khi Copilot. |
| **Build context** | Bắt đầu session Copilot cho logic group này | ALEX gom logic, paths, gaps, testcase hiện có, attachment OCR → Context Pack. Luôn bấm **trước** Generate plan. |
| **Generate plan** | Sau Build context; đã sign in M365 | Copilot đề xuất plan (update / add / retire TC). Disabled nếu chưa sign in. |
| **Save plan** | Sau khi sửa bảng plan (TC, proposed ID, intent…) | Lưu plan engineer chỉnh — **bắt buộc** trước Write nếu đã sửa tay. |
| **Write test cases** | Plan đã OK | Copilot viết full row (UseCase, Operation, I/O) theo lô (6 TC/lần) + tự retry NO-OP. |
| **Apply selected** | Ở bước Review, tick draft cần giữ | Ghi vào workbook thật. Bỏ tick draft **NO-OP** (Copilot không đổi gì). |
| **Attach / screenshot** | Có ảnh spec / bảng ngoài file Word | OCR → evidence trong Context Pack. |
| **Style samples** | Muốn Copilot bám format công ty | Upload file mẫu testcase (JSON/CSV) làm golden rows. |

**Ô Engineer knowledge:** ghi range, rule, nghĩa signal — được parse vào context (vd `OK_SHUTOFF >= 1, < 5`).

### Panel Verification patterns (cùng tab Logic)

| Nút | Ý nghĩa |
|-----|---------|
| **Promote** (1→N) | Lưu pattern “cùng Given, khác Then” — Copilot lần sau biết cần assert đủ biến thể. |
| **Promote missing Then** | TC thiếu signal Then so với sibling — nhắc Copilot bổ sung assert. |

---

## Tab Logic / Export — Test case editor

| Field / nút | Ghi chú |
|-------------|---------|
| **TestCase ID, Test Function, Event** | Sửa tên/metadata — Save row. Đổi ID → hệ thống cập nhật overlay + draft Test Code. |
| **UseCase / Operation / Expected I/O** | Badge **Engineer** = đã save, Python không ghi đè. **Auto** = còn từ pipeline. |
| **Remember I/O → code variable map** | Tick khi save → nhớ map spec signal → `in.SIG` / `out.SIG` cho Test Code. |
| **Save row** | Luôn bấm sau chỉnh sửa. |
| **Open in Test Code** | Nhảy tab Test Code đúng testcase. |
| **Improve I/O (AI)** | Copilot polish I/O một dòng — cần M365; dùng khi draft gần đúng, cần chỉnh wording. |

---

## Tab Test Code

Chọn testcase từ dropdown (cùng danh sách Final File). **Before / After** = Expected input / output đã lưu trên Export.

Luồng khuyến nghị lần đầu module:

```text
Upload .cpp mẫu → Attach .cpp → chọn Reference test → Save harness → Library
→ Save row I/O trên Export → Generate with Copilot → review → Save → .cpp
```

Lần sau cùng module: harness đã trong `web_data/.alex/` — chỉ cần chọn TC và Generate / Batch.

### Code samples (Copilot style)

Upload **1–3 file `.cpp`** mẫu từ project (panel **Code samples** hoặc upload code cùng spec ở Review). Copilot dùng mẫu cho **fixture, helper, comment style** — **không** copy giá trị signal từ mẫu (tránh leak data test cũ).

| Control | Ý nghĩa | Hiệu quả |
|---------|---------|----------|
| **Attach .cpp** | Trích `TEST_F` blocks + gợi ý harness | Auto điền Fixture / Members / Evaluate |
| **Reference test** | Chọn TEST_F làm style anchor | Code output gần format team nhất |
| **Engineer note** | Quy ước thêm (timing, helper) | Giảm chỉnh tay sau Generate |
| **Library** | Lưu harness + samples vào `web_data/.alex/` | Module/job sau không upload lại `.cpp` |

### Nút sinh code

| Nút | Khi nào | Tốc độ / chất lượng |
|-----|---------|---------------------|
| **Regenerate** | Luôn dùng được; chưa có M365 | ⚡ Vài giây — skeleton assert theo I/O |
| **Generate with Copilot** | Sign in + I/O đã Save + (khuyến nghị) code sample | 🐢 30s–2 phút/TC — code giống project thật |
| **Batch Copilot** | Nhiều TC cùng logic group | Tuần tự từng TC trong lô; bảng **Batch results** review trước Save |
| **Apply Copilot** | Sau Generate | Đưa draft vào editor — **Save** mới ghi job |
| **Copy / .cpp / Save** | Code OK | Export file hoặc giữ engineer edits |

**Batch Copilot:** tick các TC cùng nhóm logic → bấm Batch → đợi từng dòng trong bảng kết quả → **Save** từng TC đã OK. Không Save = không ghi vào bundle.

### Harness defaults

`Fixture`, `Members`, `Evaluate` — thường auto từ file `.cpp` mẫu. **Save harness** lưu job hiện tại; **Library** ghi vào `web_data/.alex/gtest_harness_preset.yaml` + project memory (dùng lại toàn server).

---

## Tab Review — M365

| Trạng thái header | Ý nghĩa |
|-------------------|---------|
| **M365 Sign In Required** | Bấm Sign in trên tab Review — Copilot + Generate with Copilot disabled. |
| **Ollama Unavailable** | Bỏ qua — ALEX v0.3 không dùng Ollama cho AI chính. |

Sign in xong → quay Logic (plan/write) hoặc Test Code (Generate with Copilot).

---

## Gửi bản sạch sang máy công ty

Trước khi zip, trên máy dev:

```bash
cd ALEX
python scripts/sanitize_for_company_deploy.py
```

Script xóa token M365, upload cũ, job phân tích, path cá nhân trong `web_data/`.  
Zip **chỉ folder `ALEX/`** (không gồm `.venv`).

---

## Cập nhật phiên bản mới

1. **Backup** `web_data/` (gồm `.alex/`) và `.env`  
2. Tải ZIP mới từ GitHub, giải nén  
3. Copy `web_data/` + `.env` + `config.yaml` đã sửa IP vào folder ALEX mới  
4. Trong folder ALEX mới:

```bash
source .venv/bin/activate   # hoặc ./cai_dat.sh nếu chưa có .venv
pip install -r requirements.txt
./chay.sh
```

5. Hard refresh browser: **Ctrl+Shift+R** (tránh JS cache cũ)

---

## Dev local (MacBook)

**Không dùng `config.yaml`** trên Mac — file đó dành cho Ubuntu server (`production`, LAN, login team).

```bash
cd ALEX
chmod +x dev.sh
./dev.sh
```

Mở http://127.0.0.1:8765 — **không cần login**, **không cần worker** (`mode: local`).

Secret: `cp .env.example .env` → điền `M365_CLIENT_SECRET` (file `.env` không commit git).

| File | Máy |
|------|-----|
| `config.yaml` | Ubuntu server công ty |
| `config.local.yaml` | Mac dev ( `./dev.sh` tự chọn ) |

Muốn test login trên Mac: sửa `team_auth.enabled: true` trong `config.local.yaml`.

---

## Dev local (chi tiết / WSL)

```bash
cd ALEX
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./dev.sh
```

WSL test production config (`config.yaml`): `./chay.sh` — một terminal, worker tự chạy nền.

Mở http://127.0.0.1:8765

**WSL + LAN:** `localhost` hoạt động trên máy host; IP `10.88.152.11` chỉ đúng khi chạy trên server Ubuntu có IP đó. Share từ WSL cần portproxy Windows → xem IT.

---

## Chạy test

```bash
cd ALEX
source .venv/bin/activate
pytest tests/ -q
```

Một số test cần file trong `sample_inputs/` (vd `GPT_GenLogic.xlsx`) — thiếu file thì test tự skip.

---

## Tóm tắt nhanh

```text
Download ZIP → unzip → cd ALEX
Sửa config.yaml: deployment.lan_ipv4 + public_url (IP thật)
./scripts/ubuntu_preflight.sh → ./cai_dat.sh → điền .env → ./chay.sh
Terminal 2: ./scripts/ubuntu_verify.sh
Login: http://<IP-server>:8765/login  ·  admin / Alex@2025!

Workflow: Review → Logic (+ Copilot plan/write) → Export → Test Code (+ .cpp sample + Batch)
Runtime data: web_data/ + web_data/.alex/  ·  Huong dan: docs/HUONG_DAN_CAI_DAT_UBUNTU.md
```
