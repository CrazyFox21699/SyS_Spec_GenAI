# Ubuntu — xử lý lỗi nâng cao

**Cài mới / quy trình đầy đủ:** đọc [CAI_UBUNTU_DON_GIAN.md](./CAI_UBUNTU_DON_GIAN.md) trước.

---

## systemd (chạy nền)

```bash
sudo cp deploy/alex.service.example /etc/systemd/system/alex.service
# Sửa WorkingDirectory = /path/to/ALEX, User, EnvironmentFile=.env
sudo systemctl daemon-reload
sudo systemctl enable --now alex
journalctl -u alex -f
```

---

## M365 Sign in — checklist

1. `.env`: `M365_CLIENT_SECRET` = **Value** (không phải Secret ID)
2. `config.yaml`: `client_id`, `tenant_id`
3. Azure: **Allow public client flows: Yes**
4. `./scripts/ubuntu_m365_ssl_check.sh` → OK
5. Restart `./chay.sh`
6. Work account (không phải Microsoft cá nhân)

---

## Review / job treo

```bash
tail -f /tmp/alex-worker.log
```

`deployment.mode` phải là `production` trên server team.

---

## Phân quyền thư mục

```bash
mkdir -p web_data/uploads web_data/output
chmod -R u+rwX web_data
```

User chạy `./chay.sh` phải sở hữu folder ALEX.

---

## Liên hệ IT

[IT_REQUEST_CHECKLIST.md](./IT_REQUEST_CHECKLIST.md)
