# SyS Spec GenAI — ALEX

Công cụ phân tích spec và sinh test case cho engineer power-mode.

**App:** folder [`ALEX/`](ALEX/)

---

## Cài trên Ubuntu server (LAN)

**Hướng dẫn đầy đủ:** [`ALEX/docs/CAI_UBUNTU_DON_GIAN.md`](ALEX/docs/CAI_UBUNTU_DON_GIAN.md)

```bash
# Lần đầu
git clone https://github.com/CrazyFox21699/SyS_Spec_GenAI.git
cd SyS_Spec_GenAI/ALEX
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh

# Điền .env + config.yaml → kiểm tra SSL → chạy
nano .env
nano config.yaml
./scripts/ubuntu_m365_ssl_check.sh
./chay.sh
```

Browser: `http://<IP-máy>:8765/login` — `admin` / `Alex@2025!`

**Mỗi ngày:** `cd ALEX && ./chay.sh`

**Dev trên Mac:** [`ALEX/README.md`](ALEX/README.md) → `./dev.sh`

```text
SyS_Spec_GenAI/
  └── ALEX/
        setup_ubuntu.sh   ← cài lần đầu (Ubuntu)
        chay.sh           ← chạy hàng ngày
        config.yaml
        docs/CAI_UBUNTU_DON_GIAN.md
```
