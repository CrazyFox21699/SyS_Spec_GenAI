# Import `alex_code_config_bundle.md` (Project Code Config)

ALEX nhận bundle Markdown từ Copilot (có escape `\_`, `\=====`, v.v.), **không validate YAML lúc import** — chỉ normalize + tách section + ghi file. YAML được kiểm tra sau khi chạy **Check Mapping Coverage** / **Generate Local from Template**.

## Đã import sẵn cho job hiện tại

| Mục | Giá trị |
|-----|---------|
| Job | `analysis_20260601_112120_245a66` |
| Nguồn bundle | `tests/fixtures/copilot_config_bundle_real.md` |
| Thư mục config | `web_data/output/<job_id>/bundle/code_config/` |
| Layer ghi | `layers/project_overrides/` (+ bản flat cùng tên để UI đọc) |
| Archive | `bundle/code_config/alex_code_config_bundle.md` (đã normalize) |

**5 section:** `code_rules.md`, `signal_mapping.yaml`, `gtest_template.md`, `api_catalog.yaml`, `ai_review_pack.md`

Trên UI: mở **Test Code → Advanced → Project Code Config**, **F5** (hoặc đổi testcase rồi quay lại) — năm editor sẽ có nội dung đã import. Không cần paste/import tay nữa.

Nếu **Preview import diff** báo `404`: restart dev server (`./dev.sh`) để load route mới:

- `POST /api/review/project-code-config/preview-bundle`
- `POST /api/review/project-code-config/apply-bundle-import`

## Import bằng CLI (không qua UI)

```bash
cd ALEX
source .venv/bin/activate

# Preview
python scripts/import_config_bundle.py analysis_20260601_112120_245a66 --dry-run

# Import fixture PM mặc định
python scripts/import_config_bundle.py analysis_20260601_112120_245a66

# Import file Copilot khác
python scripts/import_config_bundle.py <job_id> /path/to/alex_code_config_bundle.md
```

## Import qua UI (tùy chọn)

1. Paste bundle vào ô **Import bundle markdown**.
2. **Preview import diff** — xem detected / missing / warnings (`YAML validation: not_performed`).
3. **Import bundle** — ghi section vào config job.

## Sau khi import

1. Rà soát `signal_mapping.yaml` trong editor (indent, `mappings:` nếu cần cho tool sau).
2. **Check Mapping Coverage** — lúc này mới parse YAML; nếu lỗi: sửa indentation/quoting rồi chạy lại.
3. **Generate Local from Template** / Quality gate theo workflow Test Code.

## Cấu trúc file

```
bundle/code_config/
  alex_code_config_bundle.md      # bản normalize lần import cuối
  code_rules.md                   # flat (ưu tiên hiển thị = override)
  signal_mapping.yaml
  ...
  layers/
    baseline/                     # mặc định ALEX
    project_overrides/            # nội dung import Copilot
  config_versions.json            # lịch sử version
```

## Quy tắc sản phẩm

| Bước | YAML validate? |
|------|----------------|
| Preview / Import bundle | **Không** |
| Check Mapping Coverage | **Có** (parser Copilot top-level + fallback nếu YAML lỗi) |
| Generate Local from Template | **Có** |
| Quality gate | **Có** (api_catalog section + wildcard `Rte_Read_*`) |

**Advanced → Refresh Config Diagnostics** — đếm mapping keys / API entries / wildcard / YAML status.

Parser hỗ trợ `signal_mapping.yaml` dạng top-level (`WMODE_CMD:` …) và `api_catalog.yaml` dạng section (`core:`, `mocks:`, …).

Fixture regression test: `tests/test_config_bundle_import.py` + `tests/fixtures/copilot_config_bundle_real.md`.
