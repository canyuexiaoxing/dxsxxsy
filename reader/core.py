import io
from pathlib import Path
import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError
from .models import InputError, MaterialResult, PageResult
from .vision import VisionError

MAX_FILE_BYTES = 20*1024*1024
MAX_TEXT_CHARS = 100000
MAX_PDF_PAGES = 30


def safe_filename(name):
    name = str(name).replace('\\','/').split('/')[-1].replace('\x00','')
    return name[:180] or 'material'


class MaterialReader:
    def __init__(self, vision): self.vision = vision

    def read_text(self, text: str):
        if not text.strip(): raise InputError('文字内容不能为空')
        if len(text) > MAX_TEXT_CHARS: raise InputError('文字超过100000字符，请拆分提交')
        return MaterialResult(filename='输入文字.txt', kind='text', pages=[
            PageResult(page_number=1,text=text,method='text',status='read')])

    def _vision_page(self, data, page_number, extra_issues=None):
        try:
            result = self.vision.extract(data,'image/png')
            issues = list(result.issues) + list(extra_issues or [])
            if result.unreadable and not issues: issues.append('图片内容无法完整辨认')
            status = 'failed' if not result.text.strip() else ('partial' if issues or result.unreadable else 'read')
            return PageResult(page_number=page_number,text=result.text,method='vision',status=status,issues=issues)
        except VisionError as exc:
            return PageResult(page_number=page_number,method='vision',status='failed',issues=[str(exc)])

    def read_file(self, filename: str, data: bytes):
        name = safe_filename(filename)
        if not data: raise InputError('文件为空')
        if len(data) > MAX_FILE_BYTES: raise InputError('单文件超过20MiB，请拆分提交')
        suffix = Path(name).suffix.lower()
        if suffix == '.pdf': return self._pdf(name,data)
        if suffix not in {'.png','.jpg','.jpeg','.webp','.gif'}:
            raise InputError('本阶段支持PDF、PNG、JPEG、WebP及静态GIF')
        try:
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {'PNG','JPEG','WEBP','GIF'}: raise InputError('图片实际格式不支持')
                if getattr(image,'n_frames',1) > 1: raise InputError('多帧图片请拆分成静态图片，避免遗漏')
                if image.width*image.height > 30_000_000: raise InputError('图片超过3000万像素，请拆分提交')
                image = ImageOps.exif_transpose(image).convert('RGB')
                buffer = io.BytesIO()
                image.save(buffer,'PNG')
                if buffer.tell() > MAX_FILE_BYTES: raise InputError('图片展开后超过20MiB，请拆分提交')
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise InputError('图片损坏或无法解码') from None
        return self._result(name,'image',[self._vision_page(buffer.getvalue(),1)])

    def _pdf(self,name,data):
        try: doc = pymupdf.open(stream=data,filetype='pdf')
        except Exception: raise InputError('PDF损坏或无法读取') from None
        with doc:
            if doc.needs_pass: raise InputError('PDF需要密码，请先解密后提交')
            if doc.page_count > MAX_PDF_PAGES: raise InputError('PDF超过30页，请拆分提交')
            if not doc.page_count: raise InputError('PDF没有页面')
            pages = []
            for index,page in enumerate(doc):
                try:
                    text = page.get_text('text',sort=True).strip()
                    image_area = sum(pymupdf.Rect(item['bbox']).get_area() for item in page.get_image_info())
                    mixed_image = image_area > page.rect.get_area()*0.15
                    broken_text = bool(text) and text.count('\ufffd')/len(text) > 0.05
                    if text and not mixed_image and not broken_text:
                        pages.append(PageResult(page_number=index+1,text=text,method='pdf_text',status='read'))
                    elif not text and not image_area and not page.get_drawings():
                        pages.append(PageResult(page_number=index+1,method='blank',status='blank'))
                    else:
                        scale = min(2.0,3000/max(page.rect.width,page.rect.height))
                        rendered = page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False).tobytes('png')
                        extra = ['页面较大，渲染时已缩放，小字需核对原文'] if scale < 1 else []
                        pages.append(self._vision_page(rendered,index+1,extra))
                except Exception:
                    pages.append(PageResult(page_number=index+1,method='pdf_text',status='failed',issues=['本页解析失败，请查看原文件']))
        return self._result(name,'pdf',pages)

    @staticmethod
    def _result(name,kind,pages):
        good = any(p.status in {'read','partial','blank'} for p in pages)
        problems = any(p.status in {'partial','failed'} for p in pages)
        status = 'failed' if not good else ('partial' if problems else 'read')
        return MaterialResult(filename=name,kind=kind,status=status,pages=pages)
