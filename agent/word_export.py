"""Render structured reports as editable Word documents; no model calls."""
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image, ImageDraw, ImageFont

LEVELS={'high':('高风险','B85646'),'attention':('需关注','B78224'),'uncertain':('待核实','69798B')}
GREEN='287B65'

def risk_chart(findings):
    counts=Counter(f.get('level') for f in findings)
    image=Image.new('RGB',(1500,300),'white'); draw=ImageDraw.Draw(image)
    font_path=Path('C:/Windows/Fonts/msyh.ttc')
    def font(size):
        return ImageFont.truetype(str(font_path),size) if font_path.exists() else ImageFont.load_default(size=size)
    for i,(level,(label,color)) in enumerate(LEVELS.items()):
        x=10+i*500
        draw.rounded_rectangle((x,10,x+475,286),radius=24,fill='#F5F8F7')
        draw.rounded_rectangle((x+24,35,x+35,247),radius=5,fill='#'+color)
        draw.text((x+65,38),label,font=font(32),fill='#'+color)
        draw.text((x+65,91),str(counts[level]),font=font(76),fill='#1D3430')
        draw.text((x+65,208),'项已标注的问题',font=font(25),fill='#6A7C77')
    buffer=BytesIO(); image.save(buffer,format='PNG'); buffer.seek(0)
    return buffer

def shade(paragraph,color):
    element=OxmlElement('w:shd'); element.set(qn('w:fill'),color)
    paragraph._p.get_or_add_pPr().append(element)

def link(paragraph,text,url):
    if urlsplit(url).scheme not in ('http','https'): return
    relationship=paragraph.part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True)
    element=OxmlElement('w:hyperlink'); element.set(qn('r:id'),relationship)
    run=OxmlElement('w:r'); properties=OxmlElement('w:rPr')
    color=OxmlElement('w:color'); color.set(qn('w:val'),GREEN); properties.append(color)
    run.append(properties); value=OxmlElement('w:t'); value.text=text; run.append(value); element.append(run)
    paragraph._p.append(element)

def render_report_docx(report,title='求职材料自查',material_names=None):
    names=material_names or {}; document=Document(); section=document.sections[0]
    section.page_width=Cm(21); section.page_height=Cm(29.7)
    section.top_margin=Cm(1.9); section.bottom_margin=Cm(1.8)
    section.left_margin=Cm(2); section.right_margin=Cm(2)
    section.header_distance=Cm(.8); section.footer_distance=Cm(.8)
    for name in ('Normal','Title','Heading 1','Heading 2','List Bullet'):
        style=document.styles[name]; style.font.name='Microsoft YaHei'
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei')
    normal=document.styles['Normal']; normal.font.size=Pt(10.5); normal.font.color.rgb=RGBColor.from_string('263D36')
    normal.paragraph_format.line_spacing=1.4; normal.paragraph_format.space_after=Pt(7)
    normal.paragraph_format.keep_together=True
    document.styles['Title'].font.color.rgb=RGBColor.from_string('1D3430')
    for name,size in [('Heading 1',17),('Heading 2',12.5)]:
        style=document.styles[name]; style.font.size=Pt(size); style.font.color.rgb=RGBColor.from_string(GREEN)
        style.paragraph_format.space_before=Pt(15); style.paragraph_format.space_after=Pt(8)
    header=section.header.paragraphs[0]; header.text='求职避坑镜  /  JOB MIRROR'
    header.runs[0].font.size=Pt(9); header.runs[0].font.color.rgb=RGBColor.from_string(GREEN)
    footer=section.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run('求职风险自查报告  ·  第 ')
    field=OxmlElement('w:fldSimple'); field.set(qn('w:instr'),'PAGE'); footer._p.append(field)
    footer.add_run(' 页')
    for run in footer.runs: run.font.size=Pt(8); run.font.color.rgb=RGBColor.from_string('71847D')
    document.core_properties.title='求职风险自查报告'; document.core_properties.author='求职避坑镜'

    def paragraph(text='',label=None,color=None):
        p=document.add_paragraph()
        if label: p.add_run(label+'  ').bold=True
        for i,line in enumerate(str(text).splitlines() or ['']):
            if i: p.add_run().add_break()
            run=p.add_run(line)
            if color: run.font.color.rgb=RGBColor.from_string(color)
        return p

    document.add_heading('求职风险自查报告',0)
    paragraph(title,color=GREEN)
    date=report.get('created_at','')
    try: date=datetime.fromisoformat(date.replace('Z','+00:00')).astimezone().strftime('%Y-%m-%d %H:%M')
    except (ValueError,AttributeError): pass
    paragraph(f'第 {report.get("version",1)} 版  |  生成时间：{date or "未记录"}',color='71847D')
    paragraph('本报告依据已提供材料进行风险提示；风险等级不是违法认定或风险概率。',color='71847D')
    document.add_heading('01  结论与风险概览',1)
    p=paragraph(report.get('summary','暂无结论')); shade(p,'EDF6F1')
    findings=report.get('findings',[])
    picture=document.add_paragraph(); picture.add_run().add_picture(risk_chart(findings),width=Cm(17))
    paragraph('图中数量来自本报告已标注风险点；未发现问题不代表已证明安全。',color='71847D')
    if findings:
        document.add_heading('问题速览',2)
        table=document.add_table(rows=1, cols=3); table.autofit=False
        widths=[Cm(2.2),Cm(5.2),Cm(9.6)]
        for column,width in zip(table.columns,widths): column.width=width
        for cell,label,width in zip(table.rows[0].cells,['风险等级','问题','建议先做'],widths):
            cell.width=width; cell.text=label
            element=OxmlElement('w:shd'); element.set(qn('w:fill'),'EDF6F1'); cell._tc.get_or_add_tcPr().append(element)
        repeat=OxmlElement('w:tblHeader'); table.rows[0]._tr.get_or_add_trPr().append(repeat)
        for finding in findings[:6]:
            row=table.add_row(); level,color=LEVELS.get(finding.get('level'),LEVELS['uncertain'])
            values=[level,finding['title'],next(iter(finding.get('suggestions',[])),'详见风险详情')]
            for cell,value,width in zip(row.cells,values,widths): cell.width=width; cell.text=value
            row.cells[0].paragraphs[0].runs[0].font.color.rgb=RGBColor.from_string(color)
            no_split=OxmlElement('w:cantSplit'); row._tr.get_or_add_trPr().append(no_split)
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.line_spacing=1.2; p.paragraph_format.space_after=Pt(7); p.paragraph_format.space_before=Pt(7)
                    for run in p.runs: run.font.size=Pt(9.5)
        if len(findings)>6: paragraph('速览展示前6项，完整内容见风险详情。',color='71847D')
    if report.get('change_reason'): paragraph(report['change_reason'],label='本版修改')
    document.add_heading('02  风险详情',1)
    sources={s['id']:s for s in report.get('sources',[])}
    if not findings: paragraph('本次未列出具体风险点。请结合分析局限理解结论。')
    for i,finding in enumerate(findings,1):
        start=len(document.paragraphs)
        level,color=LEVELS.get(finding.get('level'),LEVELS['uncertain'])
        p=document.add_heading(f'{i:02d}  {finding["title"]}  ·  {level}',2)
        p.runs[0].font.color.rgb=RGBColor.from_string(color)
        p=paragraph(finding['quote'],label='材料原文'); shade(p,'F3F6F5')
        mid=finding.get('material_id',''); page=finding.get('page_number',0)
        location='用户补充说明' if mid=='user' else names.get(mid,mid)+(f' · 第{page}页' if page else '')
        paragraph(location,label='原文位置',color='71847D')
        paragraph(finding['explanation'],label='风险说明')
        for sid in finding.get('evidence_ids',[]):
            source=sources.get(sid)
            paragraph(f'{sid} · {source["title"]} · {source["location"]}' if source else sid,label='分析依据')
        paragraph('建议行动',color=GREEN).paragraph_format.keep_with_next=True
        for suggestion in finding.get('suggestions',[]): document.add_paragraph(suggestion,style='List Bullet')
        group=document.paragraphs[start:]
        if sum(len(p.text) for p in group)<1600:
            for p in group[:-1]: p.paragraph_format.keep_with_next=True
            group[-1].paragraph_format.keep_with_next=False
    document.add_heading('03  待核实事项与分析局限',1)
    for item in report.get('limitations',[]): document.add_paragraph(item,style='List Bullet')
    if not report.get('limitations'): paragraph('原报告未单独列出局限；这不代表所有事实均已核实。')
    document.add_heading('04  依据与来源',1)
    paragraph('法条、风险提示、指南及案例分别标注；案例结论只用于个案参考。',color='71847D')
    kinds={'law':'法律条文','warning':'官方风险提示','guide':'办事与证据指南','case':'案例参考','support':'辅助资料（团队整理）'}
    for source in report.get('sources',[]):
        start=len(document.paragraphs)
        document.add_heading(f'{source["id"]}  {source["title"]}',2)
        paragraph(f'{kinds.get(source.get("kind"),"资料")} · {source["location"]}',color='71847D')
        if source.get('text'): paragraph(source['text'])
        if source.get('boundary'): paragraph(source['boundary'],label='适用边界')
        if source.get('verification_status')=='local_document_checked_official_pending':
            paragraph('仅对照用户提供的本地文书，官方真实性与完整性待核验。',label='核验状态',color='B78224')
        if source.get('verified_at'): paragraph(source['verified_at'],label='资料核对日期',color='71847D')
        if source.get('url'):
            p=paragraph(label='来源链接'); link(p,source['url'],source['url'])
        elif source.get('source_document'): paragraph(source['source_document']+' · '+source.get('source_paragraphs',''),label='本地来源')
        group=document.paragraphs[start:]
        for p in group[1:]:
            p.paragraph_format.line_spacing=1.2
            p.paragraph_format.space_after=Pt(4)
            for run in p.runs: run.font.size=Pt(9.5)
        if sum(len(p.text) for p in group)<1800:
            for p in group[:-1]: p.paragraph_format.keep_with_next=True
            group[-1].paragraph_format.keep_with_next=False
    buffer=BytesIO(); document.save(buffer); return buffer.getvalue()
