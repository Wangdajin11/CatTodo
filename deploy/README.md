# VPS 部署（异地双人使用）

两人在不同网络时，需要一台公网服务器（最低 1C1G 即可，如腾讯云/阿里云轻量）。

## 服务端

```bash
# 1. 上传项目到服务器（任选）
git clone <你的仓库地址> cattodo && cd cattodo

# 2. 安装依赖
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt

# 3. 试运行
venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8017

# 4. 用 systemd 常驻（/etc/systemd/system/cattodo.service）
[Unit]
Description=CatTodo Server
After=network.target

[Service]
WorkingDirectory=/root/cattodo
ExecStart=/root/cattodo/venv/bin/python -m uvicorn backend.app:app --host 0.0.0.0 --port 8017
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now cattodo
```

## 防火墙

- 腾讯云/阿里云：安全组放行 TCP 8017
- 服务器本机：`ufw allow 8017`（或 `firewall-cmd --add-port=8017/tcp`）

## 客户端配置（两人各自电脑）

`client\config.json`：

```json
{
  "server_url": "http://<服务器公网IP>:8017",
  "user_id": 1
}
```

另一人填 `user_id: 2`。然后 `start_client.bat` 启动即可。

## 安全建议（上线前必做）

当前版本未加鉴权，仅适合可信两人使用。建议：

1. 在 `backend/app.py` 增加简单 Token 校验（`?token=` 或 Header）
2. 若怕 IP 暴露，配置 Nginx 反代 + HTTPS（域名或 IP 证书）
