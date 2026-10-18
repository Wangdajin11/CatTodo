#!/usr/bin/env bash
# CatTodo 一键部署脚本（Ubuntu 22.04/24.04、Debian 12，需 root）
#
# 用法：
#   方式 A（已在仓库目录内，推荐私有仓库）：
#       sudo CATTODO_TOKEN=你的密钥 bash deploy/deploy.sh
#   方式 B（服务器直接克隆，公开仓库或 REPO_URL 含 PAT）：
#       sudo REPO_URL=https://<PAT>@github.com/Wangdajin11/CatTodo.git \
#            CATTODO_TOKEN=你的密钥 bash deploy/deploy.sh
#
# 可选项：
#   DOMAIN=todo.example.com   配置 Nginx 反代并尝试自动申请 HTTPS 证书
#   APP_DIR=/opt/cattodo      安装目录
#   PORT=8017                 服务监听端口（无域名时直接对外）
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/cattodo}"
PORT="${PORT:-8017}"
DOMAIN="${DOMAIN:-}"
REPO_URL="${REPO_URL:-https://github.com/Wangdajin11/CatTodo.git}"
TOKEN="${CATTODO_TOKEN:-$(openssl rand -hex 24)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> [1/6] 系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip openssl rsync ca-certificates
[ -n "$DOMAIN" ] && apt-get install -y -qq nginx certbot python3-certbot-nginx || true

echo "==> [2/6] 同步代码到 $APP_DIR"
mkdir -p "$APP_DIR"
if [ -f "$SRC_DIR/backend/app.py" ]; then
  # 从当前仓库目录同步（排除本地虚拟环境与运行产物）
  rsync -a --delete \
    --exclude 'venv/' --exclude '.venv/' --exclude '__pycache__/' \
    --exclude '*.pyc' --exclude '*.db' --exclude '*.log' \
    --exclude 'client/config.json' \
    "$SRC_DIR/" "$APP_DIR/"
elif [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi

echo "==> [3/6] Python 虚拟环境与依赖"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"

echo "==> [4/6] 写入环境文件 /etc/cattodo.env（Token 鉴权）"
umask 077
cat > /etc/cattodo.env <<EOF
CATTODO_TOKEN=$TOKEN
EOF
chmod 600 /etc/cattodo.env

echo "==> [5/6] 安装 systemd 服务"
if [ -n "$DOMAIN" ]; then
  BIND_HOST="127.0.0.1"
else
  BIND_HOST="0.0.0.0"
fi
sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__PORT__#$PORT#g" -e "s#__HOST__#$BIND_HOST#g" \
  "$APP_DIR/deploy/cattodo.service" > /etc/systemd/system/cattodo.service
systemctl daemon-reload
systemctl enable --now cattodo
systemctl restart cattodo
sleep 2

if [ -n "$DOMAIN" ]; then
  echo "==> [6/6] Nginx 反代 + HTTPS（域名 $DOMAIN）"
  sed -e "s#__DOMAIN__#$DOMAIN#g" -e "s#__PORT__#$PORT#g" \
    "$APP_DIR/deploy/nginx-cattodo.conf" > /etc/nginx/sites-available/cattodo
  ln -sf /etc/nginx/sites-available/cattodo /etc/nginx/sites-enabled/cattodo
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || \
    echo "!! HTTPS 证书自动申请失败，可稍后手动执行：certbot --nginx -d $DOMAIN"
else
  echo "==> [6/6] 放行防火墙端口 $PORT"
  if command -v ufw >/dev/null 2>&1; then
    ufw allow "${PORT}/tcp" || true
  fi
  echo "    云服务器还需在控制台安全组放行 TCP $PORT"
fi

echo ""
echo "================ 部署完成 ================"
echo "访问地址：${DOMAIN:+https://$DOMAIN}${DOMAIN:-http://<服务器公网IP>:$PORT}"
echo "鉴权 Token：$TOKEN"
echo "客户端 client/config.json 填写："
[ -n "$DOMAIN" ] && echo "  \"server_url\": \"https://$DOMAIN\""
[ -z "$DOMAIN" ] && echo "  \"server_url\": \"http://<服务器公网IP>:$PORT\""
echo "  \"token\": \"$TOKEN\""
echo "（另一人电脑 user_id 改为 2，其余相同）"
echo "=========================================="
