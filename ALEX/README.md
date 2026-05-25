# ALEX — Test Spec Assistant (v0.3)

Công cụ local cho engineer automotive / power-mode: **phân loại** tài liệu khách hàng, **trích xuất** logic điều khiển kèm evidence, **review** và **export** workbook `TestSpec_<Module>_EN.xlsx` / `_JP.xlsx`.

- **Deterministic-first** — cấu trúc AND/OR/NOT từ parser cố định, không phụ thuộc AI.
- **Review-first** — logic mơ hồ → issue + candidate bị chặn, không tự đoán.
- **AI (M365 Copilot only)** — Resolve with Copilot, Improve I/O, Translate workbook qua Microsoft 365 Copilot Chat API (cần license + Sign in). GitHub Copilot CLI **tắt** trên server multi-user.

Hướng dẫn vận hành trong app: tab **Guide** (tiếng Việt).

**Tài liệu thêm:**

| File | Nội dung |
|------|----------|
| [docs/HUONG_DAN_CAI_DAT_UBUNTU.md](docs/HUONG_DAN_CAI_DAT_UBUNTU.md) | Cài Ubuntu, firewall, `.env`, xử lý lỗi |
| [docs/M365_COPILOT_ACTIVATION_GUIDE.md](docs/M365_COPILOT_ACTIVATION_GUIDE.md) | Sign in M365 + license Copilot |
| [config/testcase_style.yaml](config/testcase_style.yaml) | Quy tắc viết testcase cho Copilot |

---

## Cấu trúc repo (sau khi dọn)

Chỉ cần folder **`ALEX/`**:

```text
ALEX/
  cai_dat.sh      # cài lần đầu (Ubuntu)
  chay.sh         # chạy server hàng ngày
  config.yaml     # cấu hình LAN / auth / AI
  run_web.py      # web UI
  sample_inputs/  # file demo (tuỳ chọn)
  web_data/       # upload, job, session (runtime)
  src/ web/ tests/
```

Không cần `power-spec-kit`, `power-mode-spec-pipeline`, hay folder cũ `pm_test_spec_assistant`.

---

## Cài trên Ubuntu server (LAN team)

**Không cần `git clone`.** Tải ZIP từ GitHub → giải nén → 2 script.

### Bước 1 — Tải mã nguồn

1. https://github.com/CrazyFox21699/SyS_Spec_GenAI  
2. **Code** → **Download ZIP** → `SyS_Spec_GenAI-main.zip`  
3. Chuyển ZIP sang máy Ubuntu (USB, shared drive…)

### Bước 2 — Giải nén

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip

cd ~
unzip SyS_Spec_GenAI-main.zip
cd SyS_Spec_GenAI-main/ALEX
```

*(Tuỳ chọn đổi tên: `mv ~/SyS_Spec_GenAI-main ~/alex-repo` rồi `cd ~/alex-repo/ALEX`)*

### Bước 3 — Cài (1 lần)

```bash
chmod +x cai_dat.sh chay.sh scripts/ubuntu_preflight.sh scripts/ubuntu_verify.sh
./scripts/ubuntu_preflight.sh   # tuỳ chọn — kiểm tra IP, port, python
./cai_dat.sh
cp .env.example .env              # nếu script chưa tạo — dán secret IT
chmod 600 .env
sudo ufw allow 8765/tcp
```

Đợi đến khi thấy **`=== Xong ===`**. Chi tiết + troubleshooting: **[docs/HUONG_DAN_CAI_DAT_UBUNTU.md](docs/HUONG_DAN_CAI_DAT_UBUNTU.md)**.

### Bước 4 — Chạy server (mỗi ngày)

**Một terminal duy nhất** — worker chạy nền, web ở foreground. `Ctrl+C` dừng cả hai.

```bash
cd ~/SyS_Spec_GenAI-main/ALEX
./chay.sh
```

Không cần AI để chạy web + phân tích spec. **Resolve with Copilot**, **Improve I/O**, và **Translate to Japanese** cần Sign in M365 Copilot trên tab Review.

Sau khi IT gửi **Secret Value**, tạo file `.env` trên server (xem mục **Bảo mật client secret** bên dưới).

Rồi chạy lại `./chay.sh`.

Terminal khác (kiểm tra server sống):

```bash
./scripts/ubuntu_verify.sh
```

### Bước 5 — Đăng nhập

| | |
|---|---|
| Link | `http://<IP-LAN>:8765/login` — IP lấy từ `hostname -I` hoặc output `./cai_dat.sh` |
| User | `admin` |
| Pass | `Alex@2025!` *(có dấu `!` cuối)* |

Đồng nghiệp Windows/LAN: cùng link — chỉ mở browser, không cài gì.  
Tạo user mới: `/admin` (cần quyền admin).

---

## Sửa IP server

Nếu IP máy **khác** `10.88.152.11`, sửa `config.yaml`:

```yaml
deployment:
  host: 0.0.0.0
  port: 8765
  lan_ipv4: <IP-may-ban>
  public_url: http://<IP-may-ban>:8765
```

Rồi chạy lại `./chay.sh`.

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

- **Logic / Export / Test Code** — focus editor: sửa TestCase ID, Test Function, Event, I/O; badge **Engineer** = không bị Python ghi đè.
- **Copilot testcase session** — plan editable → Save plan → Write → Apply selected.
- **Test Code hybrid** — Regenerate (offline) + Generate with Copilot (M365).
- **Project memory** — IO map, verification patterns; Write theo lô + NO-OP retry.

---

## Workflow engineer (thứ tự hiệu quả)

```text
1. Review        Upload spec → Review specification → đợi job xong
2. Logic         Duyệt logic tree, Definitions, (tuỳ chọn) Verification patterns → Promote
3. Copilot       Build context → Generate plan → Save plan → Write → Apply selected
4. Export        Sửa testcase (ID, I/O) → Save row → Export Excel
5. Test Code     Regenerate hoặc Generate with Copilot → Save → .cpp
```

**M365 chưa sign in:** bước 3 dùng **Apply locally**; bước 5 chỉ **Regenerate** (Python skeleton). **Ollama Unavailable** trên header — bình thường, không cần cài Ollama.

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

Chọn testcase từ dropdown (cùng danh sách Final File). **Before / After** = Expected input / output đã lưu.

| Nút | Khi nào | Ghi chú |
|-----|---------|---------|
| **Regenerate** | Luôn dùng được (offline) | Python skeleton GTest từ I/O + harness. **Bấm đầu tiên** để xem khung code. |
| **Generate with Copilot** | Đã sign in M365 + testcase có I/O rõ | Copilot viết/refine `TEST_F` từ context + baseline. Disabled = chưa sign in (như screenshot *Sign In Required*). |
| **Apply Copilot** | Sau Generate with Copilot | Đưa bản Copilot vào editor — review rồi **Save**. |
| **Copy / .cpp** | Code OK | Export snippet. |
| **Save** | Sau sửa tay editor | Giữ engineer edits cho testcase này. |

### Rename map (optional)

Chỉ mở khi **tên spec ≠ tên biến C++** (vd spec `VEH_SPD` → code `in.vehicle_speed`).

| Nút | Ý nghĩa |
|-----|---------|
| **Suggest** | Gợi ý map từ testcase đang chọn. |
| **Apply** | Lưu map + **Regenerate** lại code. |
| **Library** | Lưu harness + map vào thư mục Library (dùng lại project sau). |

### Harness defaults

`Fixture`, `Members` (in/out), `Evaluate` — khớp project C++ thật. **Save harness** trước Regenerate hàng loạt.

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

1. Tải ZIP mới từ GitHub  
2. Giữ lại `web_data/` cũ nếu cần upload/job  
3. Chạy lại `./cai_dat.sh` nếu folder mới hoàn toàn  

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
./scripts/ubuntu_preflight.sh → ./cai_dat.sh → cp .env.example .env → ./chay.sh
Login: http://<IP-server>:8765/login  ·  admin / Alex@2025!
Huong dan Ubuntu: docs/HUONG_DAN_CAI_DAT_UBUNTU.md
```
