from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata
root=Path(SPECPATH).parent
datas=[(str(root/'frontend/dist/client'),'frontend/dist/client'),(str(root/'assets/app-icon.ico'),'assets'),(str(root/'knowledge/entries.json'),'knowledge'),(str(root/'knowledge/public-seed.json'),'knowledge'),(str(root/'knowledge/support/boundary_rules.txt'),'knowledge/support')]
binaries=[]
hiddenimports=['uvicorn.logging','uvicorn.loops.auto','uvicorn.protocols.http.auto','uvicorn.protocols.http.h11_impl','uvicorn.protocols.websockets.auto','uvicorn.lifespan.on','chromadb.api.rust','chromadb.segment.impl.vector.local_persistent_hnsw','chromadb.segment.impl.metadata.sqlite','chromadb.telemetry.product.posthog','chromadb.db.impl.sqlite','chromadb.execution.executor.local','chromadb.quota.simple_quota_enforcer','chromadb.rate_limit.simple_rate_limit','chromadb.config','chromadb_rust_bindings','webview.platforms.edgechromium','webview.platforms.winforms','reader.api','agent.routes']
for package in ('chromadb','webview'):
    d,b,h=collect_all(package);datas+=d;binaries+=b;hiddenimports+=h
for package in ('chromadb','onnxruntime','tokenizers','tqdm'):
    datas+=copy_metadata(package)
ollama=root/'runtime/ollama'
datas += [(str(ollama/'ollama.exe'),'runtime/ollama')]
for path in (ollama/'lib/ollama').rglob('*'):
    if path.is_file() and not any(part.startswith('cuda_') for part in path.parts):
        datas.append((str(path),str(Path('runtime/ollama/lib/ollama')/path.relative_to(ollama/'lib/ollama').parent)))
a=Analysis([str(root/'desktop.py')],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=hiddenimports,excludes=['pytest','IPython','notebook','matplotlib','torch','tensorflow'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='JobMirror',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon=str(root/'assets/app-icon.ico'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='JobMirror')
