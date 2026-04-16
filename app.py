"""
LocaShot Local - 图片多语言本地化工具 v2
使用 EasyOCR 做文字识别，支持中日韩英等多语言
"""
import os
import io
import json
import uuid
import base64
import colorsys
from pathlib import Path
from collections import Counter
from flask import Flask, request, jsonify, send_from_directory, send_file
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import easyocr
from deep_translator import GoogleTranslator

app = Flask(__name__, static_folder='static')
UPLOAD_DIR = Path('uploads')
OUTPUT_DIR = Path('outputs')
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# EasyOCR reader（延迟初始化，首次使用时加载模型）
_readers = {}

def get_reader(langs):
    """获取或创建 EasyOCR reader"""
    key = tuple(sorted(langs))
    if key not in _readers:
        print(f"🔄 加载 EasyOCR 模型: {langs}")
        _readers[key] = easyocr.Reader(langs, gpu=False)
        print(f"✅ 模型加载完成")
    return _readers[key]

# OCR 语言映射
OCR_LANG_MAP = {
    'zh-CN': ['ch_sim', 'en'],
    'zh-TW': ['ch_tra', 'en'],
    'ja': ['ja', 'en'],
    'ko': ['ko', 'en'],
    'en': ['en'],
    'fr': ['fr', 'en'],
    'de': ['de', 'en'],
    'es': ['es', 'en'],
    'pt': ['pt', 'en'],
    'it': ['it', 'en'],
    'ru': ['ru', 'en'],
    'ar': ['ar', 'en'],
    'hi': ['hi', 'en'],
    'th': ['th', 'en'],
    'vi': ['vi', 'en'],
}

# 支持的目标语言
LANGUAGES = {
    'en': {'name': 'English', 'flag': '🇬🇧'},
    'zh-CN': {'name': '中文', 'flag': '🇨🇳'},
    'ja': {'name': '日本語', 'flag': '🇯🇵'},
    'ko': {'name': '한국어', 'flag': '🇰🇷'},
    'es': {'name': 'Español', 'flag': '🇪🇸'},
    'fr': {'name': 'Français', 'flag': '🇫🇷'},
    'de': {'name': 'Deutsch', 'flag': '🇩🇪'},
    'pt': {'name': 'Português', 'flag': '🇧🇷'},
    'ru': {'name': 'Русский', 'flag': '🇷🇺'},
    'ar': {'name': 'العربية', 'flag': '🇸🇦'},
    'hi': {'name': 'हिन्दी', 'flag': '🇮🇳'},
    'it': {'name': 'Italiano', 'flag': '🇮🇹'},
    'tr': {'name': 'Türkçe', 'flag': '🇹🇷'},
    'vi': {'name': 'Tiếng Việt', 'flag': '🇻🇳'},
    'th': {'name': 'ไทย', 'flag': '🇹🇭'},
    'id': {'name': 'Bahasa', 'flag': '🇮🇩'},
    'nl': {'name': 'Nederlands', 'flag': '🇳🇱'},
    'pl': {'name': 'Polski', 'flag': '🇵🇱'},
    'sv': {'name': 'Svenska', 'flag': '🇸🇪'},
    'ms': {'name': 'Malay', 'flag': '🇲🇾'},
}

# 字体路径（兼容 macOS 和 Linux/Docker）
FONT_PATHS_CJK = [
    # Linux (Docker with fonts-noto-cjk)
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
    # macOS
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
    '/Library/Fonts/Arial Unicode.ttf',
]
FONT_PATHS_LATIN = [
    # Linux
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
    # macOS
    '/System/Library/Fonts/Helvetica.ttc',
    '/System/Library/Fonts/SFNSText.ttf',
    '/Library/Fonts/Arial.ttf',
]
FONT_PATHS_ARABIC = [
    # Linux
    '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    # macOS
    '/System/Library/Fonts/GeezaPro.ttc',
    '/Library/Fonts/Arial.ttf',
]

def is_cjk(text):
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF or 0x3040 <= cp <= 0x30FF or
            0xAC00 <= cp <= 0xD7AF or 0x3400 <= cp <= 0x4DBF):
            return True
    return False

def is_arabic(text):
    for ch in text:
        if 0x0600 <= ord(ch) <= 0x06FF:
            return True
    return False

def get_font(size, text=''):
    paths = FONT_PATHS_LATIN
    if is_cjk(text):
        paths = FONT_PATHS_CJK
    elif is_arabic(text):
        paths = FONT_PATHS_ARABIC

    for fp in paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                continue
    # fallback: try all
    for fp in FONT_PATHS_CJK + FONT_PATHS_LATIN:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                continue
    return ImageFont.load_default()


def get_dominant_color(img, region):
    """获取区域的主色调（用于背景填充）"""
    x1, y1, x2, y2 = region
    # 扩展采样区域
    pad = 5
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(img.width, x2 + pad)
    y2 = min(img.height, y2 + pad)

    crop = img.crop((x1, y1, x2, y2))
    # 缩小加速
    crop = crop.resize((max(1, crop.width // 4), max(1, crop.height // 4)))
    pixels = list(crop.getdata())
    if not pixels:
        return (128, 128, 128)

    # 取边缘像素的众数作为背景色
    edge_pixels = []
    w, h = crop.size
    for px_idx, px in enumerate(pixels):
        px_x = px_idx % w
        px_y = px_idx // w
        if px_x < 2 or px_x >= w - 2 or px_y < 2 or px_y >= h - 2:
            edge_pixels.append(px[:3])

    if edge_pixels:
        # 量化颜色后取众数
        quantized = [(r // 16 * 16, g // 16 * 16, b // 16 * 16) for r, g, b in edge_pixels]
        most_common = Counter(quantized).most_common(1)[0][0]
        return most_common
    return pixels[0][:3]


def get_text_color(bg_color):
    """根据背景色计算合适的文字颜色"""
    r, g, b = bg_color
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return (255, 255, 255) if brightness < 128 else (0, 0, 0)


def inpaint_region(img, x1, y1, x2, y2):
    """用周围像素修复文字区域（简单的边缘扩展填充）"""
    pad = 8
    sx1 = max(0, x1 - pad)
    sy1 = max(0, y1 - pad)
    sx2 = min(img.width, x2 + pad)
    sy2 = min(img.height, y2 + pad)

    # 取周围区域
    surround = img.crop((sx1, sy1, sx2, sy2))
    # 模糊处理来模拟背景
    blurred = surround.filter(ImageFilter.GaussianBlur(radius=max(3, (x2 - x1) // 8)))

    # 只替换文字区域
    result = img.copy()
    inner_x1 = x1 - sx1
    inner_y1 = y1 - sy1
    inner_x2 = x2 - sx1
    inner_y2 = y2 - sy1
    inner_region = blurred.crop((inner_x1, inner_y1, inner_x2, inner_y2))
    result.paste(inner_region, (x1, y1))
    return result


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/languages')
def list_languages():
    return jsonify(LANGUAGES)


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """上传图片并用 EasyOCR 识别文字"""
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    source_lang = request.form.get('source_lang', 'en')
    project_id = str(uuid.uuid4())[:8]

    project_dir = UPLOAD_DIR / project_id
    project_dir.mkdir(exist_ok=True)
    img_path = project_dir / 'original.png'
    file.save(str(img_path))

    img = Image.open(img_path)

    # 用 EasyOCR 识别
    ocr_langs = OCR_LANG_MAP.get(source_lang, ['en'])
    reader = get_reader(ocr_langs)
    results = reader.readtext(str(img_path))

    text_blocks = []
    for (bbox, text, conf) in results:
        if conf < 0.2 or not text.strip():
            continue
        # bbox 是 4 个点的坐标 [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x = int(min(xs))
        y = int(min(ys))
        w = int(max(xs) - min(xs))
        h = int(max(ys) - min(ys))

        text_blocks.append({
            'id': len(text_blocks),
            'text': text.strip(),
            'x': x, 'y': y, 'w': w, 'h': h,
            'conf': round(conf, 2),
        })

    project_info = {
        'id': project_id,
        'source_lang': source_lang,
        'width': img.width,
        'height': img.height,
        'text_blocks': text_blocks,
    }
    with open(project_dir / 'project.json', 'w') as f:
        json.dump(project_info, f, ensure_ascii=False)

    return jsonify(project_info)


@app.route('/api/translate', methods=['POST'])
def translate_text():
    """翻译文字到目标语言"""
    data = request.json
    project_id = data['project_id']
    target_langs = data['target_langs']

    project_dir = UPLOAD_DIR / project_id
    with open(project_dir / 'project.json') as f:
        project = json.load(f)

    source_lang = project['source_lang']
    texts = [b['text'] for b in project['text_blocks']]

    results = {}
    for lang in target_langs:
        if lang == source_lang:
            results[lang] = list(texts)
            continue
        try:
            translator = GoogleTranslator(source=source_lang, target=lang)
            translated = []
            for t in texts:
                try:
                    tr = translator.translate(t)
                    translated.append(tr if tr else t)
                except:
                    translated.append(t)
            results[lang] = translated
        except Exception as e:
            print(f"翻译到 {lang} 失败: {e}")
            results[lang] = list(texts)

    with open(project_dir / 'translations.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False)

    return jsonify({'translations': results})


@app.route('/api/render', methods=['POST'])
def render_image():
    """渲染翻译后的图片——先修复原文字区域，再绘制新文字"""
    data = request.json
    project_id = data['project_id']
    lang = data['lang']
    translations = data.get('translations', None)

    project_dir = UPLOAD_DIR / project_id
    with open(project_dir / 'project.json') as f:
        project = json.load(f)

    if translations is None:
        trans_path = project_dir / 'translations.json'
        if trans_path.exists():
            with open(trans_path) as f:
                all_trans = json.load(f)
            translations = all_trans.get(lang, [b['text'] for b in project['text_blocks']])
        else:
            translations = [b['text'] for b in project['text_blocks']]

    # 打开原图
    img = Image.open(project_dir / 'original.png').convert('RGB')

    # 第一步：用 inpainting 擦除所有原文字区域
    for block in project['text_blocks']:
        x, y, w, h = block['x'], block['y'], block['w'], block['h']
        pad = 3
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img.width, x + w + pad)
        y2 = min(img.height, y + h + pad)
        img = inpaint_region(img, x1, y1, x2, y2)

    # 第二步：在擦除后的图上绘制翻译文字
    draw = ImageDraw.Draw(img)

    for i, block in enumerate(project['text_blocks']):
        if i >= len(translations):
            break
        new_text = translations[i]
        if not new_text:
            continue

        x, y, w, h = block['x'], block['y'], block['w'], block['h']

        # 获取背景色和文字色
        bg_color = get_dominant_color(img, (x, y, x + w, y + h))
        text_color = get_text_color(bg_color)

        # 计算字体大小（适配区域高度）
        font_size = max(int(h * 0.75), 12)
        font = get_font(font_size, new_text)

        # 自动缩小字体直到文字宽度适配区域
        bbox = draw.textbbox((0, 0), new_text, font=font)
        text_w = bbox[2] - bbox[0]
        while text_w > w * 1.2 and font_size > 10:
            font_size -= 1
            font = get_font(font_size, new_text)
            bbox = draw.textbbox((0, 0), new_text, font=font)
            text_w = bbox[2] - bbox[0]

        text_h = bbox[3] - bbox[1]
        # 垂直居中
        text_y = y + (h - text_h) // 2
        draw.text((x, text_y), new_text, fill=text_color, font=font)

    # 转 base64
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()

    # 保存文件
    out_dir = OUTPUT_DIR / project_id
    out_dir.mkdir(exist_ok=True)
    img.save(out_dir / f'{lang}.png')

    return jsonify({'image': f'data:image/png;base64,{b64}', 'lang': lang})


@app.route('/api/download/<project_id>/<lang>')
def download_image(project_id, lang):
    out_path = OUTPUT_DIR / project_id / f'{lang}.png'
    if out_path.exists():
        return send_file(str(out_path), as_attachment=True, download_name=f'localized_{lang}.png')
    return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    print("🚀 LocaShot Local v2 启动中...")
    print("📍 打开浏览器访问: http://localhost:5555")
    print("⚠️  首次上传图片时需要下载 OCR 模型，请耐心等待")
    app.run(host='0.0.0.0', port=5555, debug=False)
