# Kích hoạt Microsoft 365 Copilot cho ALEX

ALEX gọi **Microsoft Graph Copilot Chat API** (delegated — token của user đang sign in).

## Trên UI

1. Tab **Review** → **Sign in to Microsoft 365**
2. Hoàn tất device login / browser login
3. Banner chuyển sang ready → các nút **Generate plan**, **Write test cases**, **Generate with Copilot** bật

## Điều kiện

| Điều kiện | Nếu thiếu |
|-----------|-----------|
| `M365_CLIENT_SECRET` trong `.env` | Sign in fail |
| `client_id` / `tenant_id` trong config | Sign in fail |
| Allow public client flows (Azure) | Token device flow fail |
| Work account + **M365 Copilot license** | Sign in OK nhưng Copilot API reject |
| Personal Microsoft (MSA) | Copilot Chat thường bị chặn |

## Khi không có Copilot license

Vẫn dùng được:

- Review spec, logic tree, export Excel
- **Apply locally** (Logic tab) — pattern Given đơn giản
- **Regenerate** Test Code — skeleton Python từ Expected I/O
- Sửa testcase thủ công trong editor

Không dùng được: Generate plan, Write test cases, Generate with Copilot, Improve I/O, Translate JP.

## Kiểm tra nhanh

Sau sign in, tab Review → trạng thái M365. Tab Logic → banner không còn "Sign in required".

API (khi đã login session browser): `GET /api/m365/status`
