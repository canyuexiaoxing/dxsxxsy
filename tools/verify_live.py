"""Explicit live API smoke check using synthetic, non-personal materials."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from reader.config import Settings
from reader.core import MaterialReader
from reader.vision import VisionClient
from reader.store import MaterialStore


def main():
    folder = ROOT/'samples'
    folder.mkdir(exist_ok=True)
    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    if not font_path.exists(): raise RuntimeError('Chinese test font unavailable')
    image = Image.new('RGB',(1100,400),'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path),32)
    lines = ['模拟测试材料（非真实合同）','培训费用：19800元。','本协议不承诺就业。','请保留金额和否定词。']
    for idx,line in enumerate(lines): draw.text((35,30+idx*80),line,font=font,fill='black')
    image_path = folder/'模拟聊天截图.png'
    image.save(image_path)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50,50),'SYNTHETIC TEST: Recruitment claims free training.',fontsize=14)
    page = doc.new_page(width=550,height=200)
    page.insert_image(page.rect,stream=image_path.read_bytes())
    doc.new_page()
    pdf_path = folder/'模拟混合材料.pdf'
    doc.save(pdf_path)
    doc.close()
    settings = Settings.load()
    reader = MaterialReader(VisionClient(settings))
    store = MaterialStore(settings.data_dir)
    checks = []
    for path in [image_path,pdf_path]:
        original = path.read_bytes()
        result = reader.read_file(path.name,original)
        store.save(result,original)
        visual = [p for p in result.pages if p.method=='vision']
        passed = bool(visual) and all('19800' in p.text and '不承诺就业' in p.text and p.status!='failed' for p in visual)
        checks.append({'filename':path.name,'material_id':result.material_id,'status':result.status,'page_count':len(result.pages),'methods':[p.method for p in result.pages],'passed':passed,'issues':[p.issues for p in result.pages]})
        print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    (ROOT/'live-verification.json').write_text(json.dumps({'synthetic_materials_only':True,'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks): raise SystemExit(1)


if __name__=='__main__': main()
