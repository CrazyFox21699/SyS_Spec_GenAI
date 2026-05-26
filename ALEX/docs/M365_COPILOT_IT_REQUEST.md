# Microsoft 365 Copilot — Yêu cầu IT (FPT / ALEX)

Tài liệu này mô tả **7 delegated permissions** Microsoft **bắt buộc** cho Copilot Chat API, cách IT cấu hình trên Azure, và mẫu email gửi IT.

**App registration:** `FSO.FA.DF.AVE - ALEX_TMC_AI`  
**Tenant:** FPT Corporation (`fpt.com`)  
**Tài liệu Microsoft:** [Copilot Chat API permissions](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/copilotroot-post-conversations)

---

## 1. Hiện trạng vs yêu cầu

| Trạng thái trên Azure (ảnh IT) | Copilot Graph API cần |
|---|---|
| User.Read, openid, profile, email, offline_access | Giữ nguyên |
| *(chưa có)* | **Sites.Read.All** |
| *(chưa có)* | **Mail.Read** |
| *(chưa có)* | **People.Read.All** |
| *(chưa có)* | **Chat.Read** |
| *(chưa có)* | **ChannelMessage.Read.All** |
| *(chưa có)* | **ExternalItem.Read.All** |
| *(chưa có)* | **OnlineMeetingTranscript.Read.All** |

**Grant admin consent** chỉ áp dụng cho permissions **đã được Add** vào app. Consent 5 quyền cơ bản **không thay thế** 7 quyền Copilot.

---

## 2. Bảy quyền — chi tiết cho IT

Tất cả là **Microsoft Graph → Delegated permissions** (không dùng Application permissions).

| # | Permission | Mô tả (Azure Portal) | Ghi chú |
|---|---|---|---|
| 1 | **Sites.Read.All** | Read items in all site collections | Microsoft liệt kê là *least privileged* cho Copilot API |
| 2 | **Mail.Read** | Read user mail | Delegated — chỉ mail user đã đăng nhập |
| 3 | **People.Read.All** | Read all users' relevant people lists | Org people graph cho Copilot context |
| 4 | **Chat.Read** | Read user chat messages | Teams chat (user context) |
| 5 | **ChannelMessage.Read.All** | Read user channel messages | Teams channel (user context) |
| 6 | **ExternalItem.Read.All** | Read items in external datasets | Connector / external content |
| 7 | **OnlineMeetingTranscript.Read.All** | Read all transcripts of online meetings | Meeting transcripts |

Microsoft ghi rõ: *"You need **all of these** Microsoft Graph permissions to successfully call the Microsoft 365 Copilot Chat API."*

### Loại permission

- **Delegated** — token chạy dưới user đã Sign in; tuân policy tenant.
- **Không** yêu cầu Application permission đọc toàn tenant không qua user.

### Bước IT trên Azure Portal

1. **Microsoft Entra ID** → **App registrations** → **FSO.FA.DF.AVE - ALEX_TMC_AI**
2. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**
3. Tìm và tick **7 quyền** ở bảng trên → **Add permissions**
4. **Grant admin consent for FPT Corporation** (một lần cho cả tenant)
5. Xác nhận cột **Status** = *Granted for FPT Corporation* cho cả 12 quyền (5 cũ + 7 mới)

### License (bước riêng, sau scopes)

User pilot cần **Microsoft 365 Copilot** license (SKU `Microsoft_365_Copilot`). Scopes alone không đủ nếu không có license.

---

## 3. Email mẫu — Tiếng Việt

**Subject:** `[FPT] Xin admin consent — 7 Graph permissions cho ALEX (Microsoft 365 Copilot Chat API)`

---

Kính gửi Anh/Chị IT / Azure Admin,

Em đang triển khai tool nội bộ **ALEX** (app Azure: **FSO.FA.DF.AVE - ALEX_TMC_AI**) để hỗ trợ team viết testcase và GTest cho automotive test specification.

Hiện app đã được **Grant admin consent** cho các quyền cơ bản (User.Read, openid, profile, email, offline_access). Tuy nhiên, để tích hợp **Microsoft 365 Copilot Chat API** (Graph `/copilot/conversations`), Microsoft **bắt buộc thêm 7 delegated permissions** — không thể giảm bớt theo tài liệu chính thức:

1. Sites.Read.All  
2. Mail.Read  
3. People.Read.All  
4. Chat.Read  
5. ChannelMessage.Read.All  
6. ExternalItem.Read.All  
7. OnlineMeetingTranscript.Read.All  

**Tài liệu tham chiếu:**  
https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/copilotroot-post-conversations  

**Đề nghị IT thực hiện:**

1. Vào App registration **FSO.FA.DF.AVE - ALEX_TMC_AI** → **API permissions**  
2. **Add a permission** → Microsoft Graph → **Delegated** → chọn 7 quyền trên  
3. **Grant admin consent for FPT Corporation** (một lần cho tenant)  
4. (Tuỳ chọn pilot) Gán license **Microsoft 365 Copilot** cho user thử nghiệm: `huytq136@fpt.com`  

**Phạm vi sử dụng:** Tool nội bộ — user Sign in bằng tài khoản FPT; mỗi thao tác Copilot gửi prompt kỹ thuật (test spec / GTest), không thay thế Copilot web. Permissions là **Delegated** (user context), không phải Application-wide.

**Nhóm / dự án:** AI Innovation — automotive test spec automation.

Em cảm ơn Anh/Chị. Nếu cần demo hoặc security review, em sẵn sàng trình bày thêm.

Trân trọng,  
[Tên]  
[Team / SĐT]

---

## 4. Email mẫu — English

**Subject:** `[FPT] Admin consent request — 7 Graph permissions for ALEX (M365 Copilot Chat API)`

---

Dear IT / Azure Admin,

We are deploying an internal tool **ALEX** (Azure app: **FSO.FA.DF.AVE - ALEX_TMC_AI**) to assist our team with automotive test specification and GTest generation.

The app already has admin consent for basic sign-in scopes (User.Read, openid, profile, email, offline_access). To use the **Microsoft 365 Copilot Chat API** (Graph `/copilot/conversations`), Microsoft **requires seven additional delegated permissions** — this is documented as mandatory and cannot be reduced:

1. Sites.Read.All  
2. Mail.Read  
3. People.Read.All  
4. Chat.Read  
5. ChannelMessage.Read.All  
6. ExternalItem.Read.All  
7. OnlineMeetingTranscript.Read.All  

**Reference:**  
https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/api/ai-services/chat/copilotroot-post-conversations  

**Requested actions:**

1. Open app **FSO.FA.DF.AVE - ALEX_TMC_AI** → **API permissions**  
2. **Add a permission** → Microsoft Graph → **Delegated** → select all seven permissions above  
3. **Grant admin consent for FPT Corporation** (one-time for the tenant)  
4. (Pilot) Assign **Microsoft 365 Copilot** license to test user(s)  

**Usage:** Internal engineering tool; users sign in with FPT work accounts. Copilot is invoked for structured test-spec prompts only. All permissions are **Delegated** (user context), not Application permissions.

**Project:** AI Innovation — automotive test spec automation.

Happy to provide a demo or security review if needed.

Best regards,  
[Name]  
[Team / contact]

---

## 5. Sau khi IT hoàn tất — checklist user

1. Review tab → **Sign out** M365 (nếu đã sign in trước đó)  
2. **Sign in** (chỉ User.Read — không cần popup 7 quyền nếu chưa Authorize Copilot)  
3. **Authorize Copilot API** → hoàn tất consent (nếu IT đã admin-consent thì pass ngay)  
4. **Test Copilot API** → badge **COPILOT OK**  
5. Import TestSpec → Generate with Copilot / Copilot improve row  

---

## 6. Nếu IT không duyệt 7 quyền

ALEX vẫn dùng được: Import TestSpec, chỉnh testcase, export Excel, **Generate GTest offline** (baseline). Chỉ các nút **Microsoft 365 Copilot** bị tắt.
