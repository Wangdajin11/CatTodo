# CatTodo VPS 部署指南

一台两人都能访问的云服务器（推荐 Ubuntu 22.04 / 24.04，1 核 1G 起步即可）。

## 方式 A：从本地上传仓库（推荐，私有仓库免配 PAT）

```bash
# 本地（Windows PowerShell）：把整个项目传到服务器（不含 venv）
scp -r D:\FunnyThing\ToDoList root@<服务器IP>:/opt/CatTodo-src

# 服务器上：
cd /opt/CatTodo-src
sudo CATTODO_TOKEN=自定义一串密钥 bash deploy/deploy.sh
```

## 方式 B：服务器直接克隆私有仓库

在 GitHub 建一个 Personal Access Token（classic，勾选 repo 权限）：

```bash
sudo REPO_URL=https://<PAT>@github.com/Wangdajin11/CatTodo.git \
     CATTODO_TOKEN=自定义一串密钥 bash deploy/deploy.sh
```

## 域名 + HTTPS（可选）

有域名且 A 记录已指向服务器时：

```bash
sudo DOMAIN=todo.example.com CATTODO_TOKEN=密钥 bash deploy/deploy.sh
```

脚本自动配置 Nginx 反代并申请 Let's Encrypt 证书；没有域名则直接暴露 `http://<IP>:8017`，记得在云控制台安全组放行 TCP 8017。

## 客户端配置

部署完成后，两人各自编辑 `client/config.json`：

```json
{
  "server_url": "http://<服务器IP>:8017",
  "user_id": 1,
  "threshold": 300,
  "token": "部署时设定的密钥"
}
```

- 一人 `user_id` 为 1，另一人改为 2；
- 有域名时 `server_url` 用 `https://你的域名`；
- 两人 token 必须相同；填错或不填会被服务端拒绝（401）。

## 安全说明

- `CATTODO_TOKEN` 是 API 与 WebSocket 的共享密钥，存于服务器 `/etc/cattodo.env`（权限 600）；
- Token 仅保护数据接口（`/api`、`/ws`），页面外壳本身不鉴权；
- 公网裸 HTTP 部署时 token 会明文传输，条件允许请使用域名 + HTTPS；
- 不设置 `CATTODO_TOKEN` 时服务端不鉴权，仅限本机 / 受信局域网使用。

## 常用运维

```bash
sudo systemctl status cattodo       # 状态
sudo systemctl restart cattodo      # 重启
sudo journalctl -u cattodo -f       # 日志
sudo cat /etc/cattodo.env           # 查看 token
```
