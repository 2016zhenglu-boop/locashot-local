FROM python:3.11-slim

# 安装系统依赖（OpenCV、字体等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    fonts-noto-cjk \
    fonts-noto-core \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载 EasyOCR 模型（避免运行时下载）
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False)"

COPY . .

# 创建上传和输出目录
RUN mkdir -p uploads outputs

# HF Spaces 使用 7860 端口
EXPOSE 7860

CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--timeout", "300", "--workers", "2", "app:app"]
