#!/bin/bash
# LocaShot Local - AWS EC2 部署脚本
# 使用方法：
# 1. 在 EC2 上运行此脚本
# 2. 确保 EC2 安全组开放了 5555 端口

set -e

echo "🚀 LocaShot Local 部署开始..."

# 安装 Docker（如果没有）
if ! command -v docker &> /dev/null; then
    echo "📦 安装 Docker..."
    sudo yum update -y 2>/dev/null || sudo apt-get update -y
    sudo yum install -y docker 2>/dev/null || sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "⚠️  Docker 已安装，请重新登录后再运行此脚本"
    exit 0
fi

echo "🔨 构建 Docker 镜像（首次约 10-15 分钟，需下载 OCR 模型）..."
docker build -t locashot-local .

echo "🛑 停止旧容器（如果有）..."
docker stop locashot 2>/dev/null || true
docker rm locashot 2>/dev/null || true

echo "🚀 启动容器..."
docker run -d \
    --name locashot \
    --restart unless-stopped \
    -p 5555:5555 \
    locashot-local

echo ""
echo "✅ 部署完成！"
echo "📍 访问地址: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<你的EC2公网IP>'):5555"
echo ""
echo "📋 常用命令："
echo "  查看日志: docker logs -f locashot"
echo "  停止服务: docker stop locashot"
echo "  重启服务: docker restart locashot"
