# 🌍 LocaShot Local

图片多语言本地化工具 - 上传图片，自动识别文字，一键翻译成 20+ 种语言并渲染到图片上。

## 功能
- 📤 拖拽上传图片
- 🔍 EasyOCR 自动识别图片中的文字（支持中日韩英等）
- 🌐 Google 翻译到 20+ 种目标语言
- 🎨 自动擦除原文字并渲染翻译后的文字
- ✏️ 支持手动编辑翻译结果
- ⬇️ 下载本地化后的图片

## 本地运行
```bash
pip install -r requirements.txt
python app.py
# 打开 http://localhost:5555
```

## Docker 运行
```bash
docker build -t locashot-local .
docker run -p 5555:5555 locashot-local
```
