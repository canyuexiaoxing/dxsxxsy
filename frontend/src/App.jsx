import React, {useEffect, useRef, useState} from 'react';
import {ShieldCheck, Plus, ChatCircleText, Sparkle, User, Warning, BookOpen, CaretDown, Paperclip, PaperPlaneRight, FilePdf, FileImage, FileText, X, DownloadSimple, ArrowUpRight, Info, List, Trash, CheckCircle, ArrowClockwise, GearSix, Eye, EyeSlash, Stop} from '@phosphor-icons/react';
import {api, jsonPost, sourceUrl} from './api.js';

function AdviceText({text}) {
  return String(text).split(/(https?:\/\/[^\s<>"\u3000-\u303f\u3400-\u9fff\uff00-\uffef]+)/g).map((part,i)=>
    /^https?:\/\//.test(part)?<a key={i} href={part} target="_blank" rel="noopener noreferrer">{part}</a>:part);
}

const labels={high:'高风险',attention:'需关注',uncertain:'待核实'};
const FileIcon=({name,...props})=>/\.pdf$/i.test(name)?<FilePdf {...props}/>: /\.(png|jpe?g|webp|bmp)$/i.test(name)?<FileImage {...props}/>:<FileText {...props}/>;
const dateText=value=>new Date(value).toLocaleDateString('zh-CN',{month:'2-digit',day:'2-digit'});

function Sources({sources}) {
  if (!sources?.length) return null;
  return <details className="sources" open><summary><BookOpen size={24}/>法规与资料依据<CaretDown className="chevron" size={18}/></summary><div className="source-list">{sources.map((s,i)=><details className="source" open={i===0} key={s.id}><summary className="source-title">{s.title} <span>{s.location}</span><CaretDown size={16}/></summary><p>{s.text}</p><div className="source-meta">{({law:'法律法规',warning:'官方风险提示',guide:'办事指南',case:'典型案例',support:'辅助资料（团队整理）'})[s.kind]||s.kind} · {s.id}</div>{s.source_publisher&&<p className="source-meta">发布机构：{s.source_publisher}</p>}{sourceUrl(s.legal_database_url)&&<a href={s.legal_database_url} target="_blank" rel="noreferrer">国家法律法规数据库查询入口（未核验具体记录）<ArrowUpRight size={15}/></a>}{s.boundary&&<details className="boundary"><summary>查看适用边界</summary><p>{s.boundary}</p></details>}{sourceUrl(s.url)&&<a href={s.url} target="_blank" rel="noreferrer">{s.kind==='support'?'查看核对依据 / 查询入口':'查看官方原文'}<ArrowUpRight size={15}/></a>}</details>)}</div></details>;
}

function Report({report,session}) {
  const [version,setVersion]=useState(report.version), [shown,setShown]=useState(report),[error,setError]=useState('');
  async function change(event) {
    const v=Number(event.target.value);setError('');
    try {setShown(await api(`/api/sessions/${session.id}/reports/${v}`));setVersion(v);} catch(e){setError(e.message);}
  }
  return <article className="report"><div className="report-header"><h2>{shown.employment_stage==='preemployment'?'求职前避坑报告':'材料风险分析报告'}</h2><select aria-label="报告版本" value={version} onChange={change}>{Array.from({length:report.version},(_,i)=><option value={i+1} key={i}>第 {i+1} 版</option>)}</select>{session.title.includes('示例')&&<span className="sample">示例</span>}</div><p className="report-summary">{shown.summary}</p>{shown.prevention&&<section className="limitations" aria-label="求职前行动建议"><h3>签约与入职前，建议先做</h3><p><strong>{shown.prevention.label}</strong></p><ul>{shown.prevention.steps.map((step,i)=><li key={i}><AdviceText text={step}/></li>)}</ul><p className="muted">{shown.prevention.note}</p></section>}<p className="muted">红灯=高风险；黄灯=需关注；灰色=待核实。未检出风险不等于绿灯安全。</p>{shown.findings.map((f,i)=><section className={`finding ${f.level}`} key={i}><div className="finding-head"><span className="risk-icon"><Warning weight="fill" size={29}/></span><div><h3>{f.title}</h3><span className="risk-label">{labels[f.level]}</span></div></div><blockquote>{f.quote}</blockquote><button className="text-link location" onClick={()=>window.dispatchEvent(new CustomEvent('material-preview',{detail:f.material_id}))}>{f.material_id==='user'?'来自你的补充说明':`查看材料原文 · 第 ${f.page_number} 页`}</button><p className="explanation">{f.explanation}</p><ul className="suggestions">{f.suggestions.map((s,j)=><li key={j}><AdviceText text={s}/></li>)}</ul></section>)}<Sources sources={shown.sources}/>{shown.limitations?.length>0&&<details className="limitations" open><summary><Info size={18}/>待核实事项与局限<CaretDown size={16}/></summary><ul>{shown.limitations.map((s,i)=><li key={i}>{s}</li>)}</ul></details>}{shown.self_checks?.length>0&&<details className="limitations" open><summary><Info size={18}/>关联自查清单<CaretDown size={16}/></summary><p>可在当前会话补充以下信息，再判断是否需要修订报告。</p><ul>{shown.self_checks.map((q,i)=><li key={i}>{q}</li>)}</ul></details>}{shown.version>1&&shown.change_reason&&<p className="change-reason">本版修改：{shown.change_reason}</p>}<a className="button download" href={`/api/sessions/${session.id}/reports/${version}/download?format=docx`} download><DownloadSimple size={18}/>下载报告<span className="muted">Word · 图文版</span></a>{error&&<p role="alert" className="error-inline">{error}</p>}</article>;
}

export function Reply({result,session,onFill}) {
  const asking=result.action==='ask';
  return <div className="message assistant"><div className="avatar agent-avatar"><Sparkle weight="fill" size={24}/></div><div className="assistant-content">{result.report?<Report report={result.report} session={session}/>:<div className="answer">{asking&&<section className="clarification-block" aria-label="需要补充的信息"><h3 className="dialogue-heading">我需要先确认</h3><ol className="questions">{result.questions.map((q,i)=><li key={i}>{q}</li>)}</ol></section>}<div className="brief-analysis">{asking&&<h3 className="dialogue-heading">根据现有信息</h3>}<p><AdviceText text={result.message}/></p></div>{asking&&<button className="button soft" onClick={()=>onFill('暂时无法补充以上信息，请先生成有限报告，并列明待核实事项。')}>暂不清楚，先给有限报告</button>}{result.sources?.length>0&&<details className="answer-sources"><summary>查看本次回答依据<CaretDown size={16}/></summary><Sources sources={result.sources}/></details>}</div>}</div></div>;
}

function ApiKeySettings({onClose}) {
  const [status,setStatus]=useState(null),[key,setKey]=useState(''),[visible,setVisible]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
  useEffect(()=>{let active=true;api('/api/settings/api-key').then(value=>{if(active)setStatus(value);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
  async function save(event) {
    event.preventDefault(); if(!key.trim()||saving)return;
    setSaving(true);setError('');setMessage('');
    try {const result=await api('/api/settings/api-key',jsonPost({api_key:key.trim()}));setStatus(result);setKey('');setVisible(false);setMessage('已保存，下次分析直接使用新 Key。');}
    catch(e){setError(e.message);} finally{setSaving(false);}
  }
  return <div className="modal-backdrop" onClick={()=>{if(!saving)onClose();}}><section className="key-settings" role="dialog" aria-modal="true" aria-labelledby="key-settings-title" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape'&&!saving){e.stopPropagation();onClose();}}}><header><div className="settings-symbol"><GearSix size={25}/></div><div><h2 id="key-settings-title">API 设置</h2><p>连接你的 DeepSeek 账号</p></div><button className="icon-button" aria-label="关闭 API 设置" disabled={saving} onClick={onClose}><X size={21}/></button></header><div className="key-status"><span className={status?.configured?'configured-dot':'unconfigured-dot'}/>{status?status.configured?'已配置 API Key':'尚未配置 API Key':'正在读取配置…'}</div><form onSubmit={save}><label htmlFor="deepseek-key">DeepSeek API Key</label><div className="key-input-wrap"><input id="deepseek-key" type={visible?'text':'password'} value={key} onChange={e=>{setKey(e.target.value);setMessage('');}} placeholder={status?.configured?'粘贴新 Key 以替换现有配置':'粘贴你的 API Key'} autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={512} disabled={saving}/><button type="button" className="icon-button" aria-label={visible?'隐藏 API Key':'显示 API Key'} onClick={()=>setVisible(v=>!v)} disabled={saving}>{visible?<EyeSlash size={20}/>:<Eye size={20}/>}</button></div><p className="settings-help">用于材料识别、风险分析和追问。保存在本机，关闭软件后仍有效；本地知识库检索无需 API Key。</p>{error&&<p role="alert" className="error-inline">{error}</p>}{message&&<p role="status" className="settings-success"><CheckCircle size={18}/>{message}</p>}<footer><span>{status?.model?`当前模型：${status.model}`:''}</span><button className="button soft" type="submit" disabled={!key.trim()||saving}>{saving?<><ArrowClockwise className="spin" size={17}/>正在保存</>:<>保存设置<CheckCircle size={17}/></>}</button></footer></form></section></div>;
}


export function App() {
  const [history,setHistory]=useState([]),[session,setSession]=useState(null),[draft,setDraft]=useState(''),[files,setFiles]=useState([]),[busy,setBusy]=useState(false),[phase,setPhase]=useState(''),[error,setError]=useState(''),[pending,setPending]=useState(null),[preview,setPreview]=useState(null),[deleteOpen,setDeleteOpen]=useState(null),[deleting,setDeleting]=useState(false),[mobile,setMobile]=useState(false),[loading,setLoading]=useState(true);
  const [settingsOpen,setSettingsOpen]=useState(false);
  const input=useRef(),scroll=useRef(),textarea=useRef(),lastSession=useRef(null),viewEpoch=useRef(0),operation=useRef(null),visibleSession=useRef(null);
  async function refresh(){const list=await api('/api/sessions');setHistory(list);return list;}
  async function open(sid){visibleSession.current=sid;const epoch=++viewEpoch.current;setLoading(true);setError('');try {const item=await api(`/api/sessions/${sid}`);if(epoch!==viewEpoch.current)return;setSession(item);setDraft('');setFiles([]);setMobile(false);localStorage.setItem('job-mirror-session',sid);window.history.replaceState(null,'',`?session=${sid}`);}catch(e){if(epoch===viewEpoch.current)setError(e.message);}finally{if(epoch===viewEpoch.current)setLoading(false);}}
  useEffect(()=>{let active=true;(async()=>{try {const list=await refresh();const sid=new URLSearchParams(location.search).get('session')||localStorage.getItem('job-mirror-session');if(active&&sid&&list.some(s=>s.id===sid))await open(sid);}catch(e){if(active)setError(e.message);}finally{if(active)setLoading(false);}})();return()=>{active=false;};},[]);
  useEffect(()=>{const initial=lastSession.current!==session?.id;lastSession.current=session?.id;scroll.current?.scrollTo({top:initial&&session?.messages?.length<=2?0:scroll.current.scrollHeight,behavior:initial||window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});},[session?.messages?.length,pending,phase]);
  async function showMaterial(id){if(id==='user'){setPreview({material_id:'user',filename:'你的补充说明',pages:[{page_number:0,method:'会话文字',text:session?.messages.filter(m=>m.role==='user').map(m=>m.text).join('\n\n')||'',issues:[]}]});return;}try{setPreview(await api(`/api/materials/${id}`));}catch(e){setError(e.message);}}
  useEffect(()=>{const handler=e=>showMaterial(e.detail);window.addEventListener('material-preview',handler);return()=>window.removeEventListener('material-preview',handler);},[session]);
  useEffect(()=>{const escape=e=>{if(e.key==='Escape'){setPreview(null);setDeleteOpen(false);setMobile(false);}};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape);},[]);
  useEffect(()=>{
    if(!preview&&!deleteOpen&&!settingsOpen)return;
    const previous=document.activeElement;
    const dialog=document.querySelector('[role="dialog"]');
    const elements=()=>[...dialog.querySelectorAll('button,a[href],input,select,textarea,[tabindex="0"]')].filter(e=>!e.disabled);
    elements()[0]?.focus();
    const trap=e=>{if(e.key!=='Tab')return;const list=elements();const first=list[0],last=list[list.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}};
    dialog.addEventListener('keydown',trap);
    return()=>{dialog.removeEventListener('keydown',trap);previous?.focus();};
  },[preview,deleteOpen,settingsOpen]);
  async function newChat(){visibleSession.current=null;++viewEpoch.current;setLoading(false);setSession(null);setFiles([]);setDraft('');setError('');setMobile(false);localStorage.removeItem('job-mirror-session');window.history.replaceState(null,'','/');textarea.current?.focus();}
  function addFiles(list){const chosen=Array.from(list);if(files.length+chosen.length>5){setError('一次最多添加 5 个文件。');return;}if(chosen.some(f=>f.size>20*1024*1024)){setError('单个文件最大 20MiB，请先拆分文件。');return;}if(chosen.some(f=>! /\.(pdf|png|jpe?g|webp|bmp)$/i.test(f.name))){setError('支持 PDF、PNG、JPG、WebP 和 BMP 文件。');return;}setError('');setFiles(old=>[...old,...chosen.map(file=>({file,name:file.name}))]);}
  async function send(event){
    event?.preventDefault();if(operation.current||(!draft.trim()&&!files.length))return;
    const op={id:crypto.randomUUID(),sid:session?.id,epoch:viewEpoch.current,cancelled:false,stopping:false};
    operation.current=op;setBusy(true);setError('');
    const submittedDraft=draft,submittedFiles=files,text=draft.trim()||'请分析这些材料。';
    let current=session,attachments=files;
    setPending({text,names:files.map(f=>f.name),sid:current?.id,epoch:op.epoch});
    const isVisible=()=>op.epoch===viewEpoch.current||(!!op.sid&&visibleSession.current===op.sid);
    try{
      if(!current){
        current=await api('/api/sessions',jsonPost({title:draft.trim().slice(0,22)||'材料风险自查'}));op.sid=current.id;
        if(op.epoch===viewEpoch.current){visibleSession.current=current.id;setSession(current);localStorage.setItem('job-mirror-session',current.id);window.history.replaceState(null,'',`?session=${current.id}`);}
        setPending(p=>p?{...p,sid:current.id}:p);await refresh();
      }
      if(op.cancelled){await api(`/api/sessions/${op.sid}/tasks/${op.id}/cancel`,{method:'POST'});return;}
      const fresh=attachments.filter(f=>!f.material_id);
      if(fresh.length){
        setPhase('正在读取材料');const form=new FormData();
        form.append('session_id',current.id);form.append('request_id',op.id);
        fresh.forEach(f=>form.append('files',f.file));
        const uploaded=await api('/api/materials',{method:'POST',body:form});const assigned=new Set();
        attachments=attachments.map(f=>{if(f.material_id)return f;const m=uploaded.materials.find(m=>m.filename===f.name&&!assigned.has(m.material_id));if(!m)return f;assigned.add(m.material_id);return {...f,material_id:m.material_id,status:m.status};});
        if(isVisible())setFiles(prev=>prev.map(f=>attachments.find(a=>a.file===f.file)||f));
        if(uploaded.errors.length)throw new Error(uploaded.errors.map(e=>`${e.filename}：${e.error}`).join('；'));
      }
      if(op.cancelled)return;
      setPhase('正在检索依据并分析');
      await api(`/api/sessions/${current.id}/messages`,jsonPost({text,material_ids:attachments.map(f=>f.material_id).filter(Boolean),request_id:op.id}));
      const updated=await api(`/api/sessions/${current.id}`);
      if(isVisible()){setSession(updated);setFiles(prev=>prev.filter(f=>!submittedFiles.some(old=>old.file===f.file)));setDraft(value=>value===submittedDraft?'':value);}
      await refresh();
    }catch(e){
      if(!op.cancelled&&isVisible()){
        setError(e.message+'。输入和附件已保留，可检查后重试。');
        try{const updated=await api(`/api/sessions/${current.id}`);if(isVisible())setSession(updated);}catch{}
      }
    }finally{
      if(op.cancelled&&isVisible()){setFiles(prev=>prev.filter(f=>!submittedFiles.some(old=>old.file===f.file)));setError('已停止本次生成，未保存本次结果；原有会话和报告保留。');}
      if(operation.current===op){operation.current=null;setBusy(false);setPending(null);setPhase('');}
    }
  }
  async function stopGeneration(){
    const op=operation.current;if(!op||op.stopping)return;
    op.stopping=true;op.cancelled=true;setPhase('正在停止并清理本次生成');
    try{
      if(op.sid){const result=await api(`/api/sessions/${op.sid}/tasks/${op.id}/cancel`,{method:'POST'});
        if(result.status==='completed'){op.cancelled=false;setPhase('任务已完成，正在读取结果');}}
    }catch(e){op.cancelled=false;op.stopping=false;setError('停止未成功：'+e.message+'。可以再次点击停止。');}
  }
  const pendingHere=!!pending&&pending.sid===session?.id&&(!!pending.sid||pending.epoch===viewEpoch.current);
  async function deleteChat(){
    if(!deleteOpen||deleting)return;
    const target=deleteOpen;setDeleting(true);
    try{
      const op=operation.current;
      if(op?.sid===target.id){op.cancelled=true;op.stopping=true;setPhase('正在停止并删除会话');}
      await api(`/api/sessions/${target.id}`,{method:'DELETE'});
      setDeleteOpen(null);
      if(visibleSession.current===target.id)await newChat();
      await refresh();
    }catch(e){setDeleteOpen(null);setError('删除未完成：'+e.message);}
    finally{setDeleting(false);}
  }
  const greeting=<div className="empty-state"><div className="welcome-symbol"><ShieldCheck weight="duotone" size={58}/></div><span className="eyebrow">从一份材料开始</span><h1>求职之前，先看清风险。</h1><p>上传招聘启事、HR聊天记录或拟签协议。<br/>先识别风险，再确认付款、贷款或签约前该核查什么。</p><div className="welcome-actions"><button className="button soft" onClick={()=>input.current.click()}><Paperclip size={18}/>添加材料</button><button className="button" onClick={()=>{setDraft('我正在找实习或工作，还没有入职。请帮我检查招聘信息中的坑，并告诉我下一步如何规避。');textarea.current?.focus();}}>先聊聊情况<ArrowUpRight size={16}/></button></div><span className="empty-note">文字 · PDF · 图片，支持一起提交</span></div>;
  return <div className="app"><aside inert={!!preview||!!deleteOpen||settingsOpen} className={`sidebar ${mobile?'mobile-open':''}`}><div className="brand"><ShieldCheck weight="duotone" size={40}/><div><strong>求职避坑镜</strong><span>大学生实习与求职前避坑助手</span></div><button className="icon-button mobile-close" aria-label="关闭会话列表" onClick={()=>setMobile(false)}><X size={20}/></button></div><button className="new-chat" onClick={newChat}><Plus size={22}/>新会话</button><div className="history-caption">最近会话</div><nav className="history" aria-label="历史会话">{history.map(s=><div key={s.id} className={`history-row ${s.id===session?.id?'selected':''}`}><button className="history-item" onClick={()=>open(s.id)}><ChatCircleText size={21}/><span>{s.title}</span><time>{dateText(s.updated_at)}</time></button><button className="icon-button history-delete" title={`删除会话：${s.title}`} aria-label={`删除会话：${s.title}`} onClick={()=>setDeleteOpen({id:s.id,title:s.title})}><Trash size={17}/></button></div>)}</nav><div className="sidebar-bottom"><p>理性求职<br/>看清风险<br/>更从容的职场起点</p><span><CheckCircle size={15}/>会话记录保存在本机</span></div></aside>{mobile&&<button className="sidebar-scrim" aria-label="收起会话列表" onClick={()=>setMobile(false)}/>}
    <main inert={!!preview||!!deleteOpen||settingsOpen}><header className="topbar"><button className="icon-button mobile-toggle" aria-label="打开会话列表" onClick={()=>setMobile(true)}><List size={23}/></button><h1>{session?.title||'新会话'}</h1><span className="local-label">本地会话</span><button className="icon-button settings-button" title="API 设置" aria-label="API 设置" onClick={()=>setSettingsOpen(true)}><GearSix size={20}/></button>{session&&<button className="icon-button delete" title="删除当前会话" aria-label="删除当前会话" onClick={()=>setDeleteOpen({id:session.id,title:session.title})}><Trash size={19}/></button>}</header><div className="conversation" ref={scroll} aria-busy={busy}>{loading?<div className="loading-empty">正在读取会话…</div>:!session?.messages?.length&&!pendingHere?greeting:<div className="conversation-inner">{session?.messages.map((m,i)=>m.role==='user'?<div className="message user-message" key={i}><div className="user-content"><div className="user-bubble">{m.text}</div>{m.material_ids?.length>0&&<div className="sent-materials">{m.material_ids.map(mid=><button className="button" onClick={()=>showMaterial(mid)} key={mid}><FileText size={17}/>查看材料</button>)}</div>}</div><div className="avatar user-avatar"><User weight="fill" size={23}/></div></div>:<Reply key={i} result={m.result} session={session} onFill={text=>{setDraft(text);textarea.current?.focus();}}/>)}{pendingHere&&<div className="message user-message"><div className="user-content"><div className="user-bubble">{pending.text}</div><div className="sent-materials">{pending.names.map((name,i)=><span className="attachment" key={i}><FileIcon name={name} size={17}/>{name}</span>)}</div></div><div className="avatar user-avatar"><User weight="fill" size={23}/></div></div>}{busy&&pendingHere&&<div className="message assistant processing" role="status"><div className="avatar agent-avatar"><Sparkle weight="fill" size={23}/></div><div><span className="activity-dots"><span/><span/><span/></span><p>{phase||'正在准备会话'}<span className="muted"> · 请稍候</span></p></div></div>}</div>}</div>
    <div className="composer-area">{busy&&<div className="generation-status" role="status"><span><ArrowClockwise className="spin" size={17}/>{phase||"正在准备生成"}{!pendingHere&&" · 原会话任务"}</span><button type="button" className="button stop-generation" onClick={stopGeneration} disabled={operation.current?.stopping}><Stop weight="fill" size={17}/>{operation.current?.stopping?"正在停止":"停止生成"}</button></div>}{error&&<div className="error-banner" role="alert"><Warning size={20}/><span>{error}</span><button className="icon-button" aria-label="关闭提示" onClick={()=>setError('')}><X size={18}/></button></div>}<form className={`composer ${busy?'is-busy':''}`} onSubmit={send} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();addFiles(e.dataTransfer.files);}}><textarea ref={textarea} aria-label="输入问题或补充信息" placeholder="粘贴招聘信息、HR聊天或拟签协议，说明是否已付款、签字或开始工作…" value={draft} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send();}}} rows={2}/><div className="composer-bottom"><div className="attachments"><button className="button attach-button" type="button" onClick={()=>input.current.click()}><Paperclip size={19}/>添加材料</button>{files.map((f,i)=><span className="attachment" key={i}><FileIcon name={f.name} size={17}/><span title={f.name}>{f.name}</span><button type="button" className="icon-button" aria-label={`移除 ${f.name}`} onClick={()=>setFiles(old=>old.filter((_,j)=>j!==i))}><X size={15}/></button></span>)}</div><button type="submit" className="send" aria-label="发送消息" disabled={busy||(!draft.trim()&&!files.length)}>{busy?<ArrowClockwise className="spin" size={23}/>:<PaperPlaneRight weight="fill" size={25}/>}</button></div><input ref={input} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp" hidden onChange={e=>{addFiles(e.target.files);e.target.value='';}}/></form><div className="composer-note"><Info size={16}/><span>材料分析会调用 AI，请核验关键结论。</span><span className="keyboard-hint">Enter 发送 · Shift + Enter 换行</span></div></div></main>
    {settingsOpen&&<ApiKeySettings onClose={()=>setSettingsOpen(false)}/>}
    {preview&&<div className="modal-backdrop" onClick={()=>setPreview(null)}><section className="material-modal" role="dialog" aria-modal="true" aria-label="材料原文" onClick={e=>e.stopPropagation()}><header><h2>{preview.filename}</h2><button className="icon-button" aria-label="关闭材料原文" onClick={()=>setPreview(null)}><X size={22}/></button></header><p className="muted">以下是提取内容，请结合原文件核验。</p>{preview.material_id!=='user'&&<a href={`/api/materials/${preview.material_id}/original`} target="_blank" rel="noreferrer" className="button">打开原文件<ArrowUpRight size={16}/></a>}<div className="material-pages">{preview.pages.map(p=><section key={p.page_number}><h3>{p.page_number===0?"用户说明":`第 ${p.page_number} 页`}<span>{p.method}</span></h3><pre>{p.text||'该页没有可读取文字。'}</pre>{p.issues?.map((issue,i)=><p className="error-inline" key={i}>{issue}</p>)}</section>)}</div></section></div>}
    {deleteOpen&&<div className="modal-backdrop"><section className="confirm-modal" role="dialog" aria-modal="true" aria-label="删除会话确认"><h2>删除这段会话？</h2><p><strong>{deleteOpen.title}</strong></p><p>聊天记录、全部报告及专属材料将从本机删除，无法恢复。共享材料、知识库和 API 设置保留；正在生成时会先停止。</p><div><button className="button" disabled={deleting} onClick={()=>setDeleteOpen(null)}>保留会话</button><button className="button danger" disabled={deleting} onClick={deleteChat}>{deleting?'正在删除…':'确认删除'}</button></div></section></div>}
  </div>;
}
