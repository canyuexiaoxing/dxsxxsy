import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4


class SessionStore:
    def __init__(self,directory:Path):
        directory.mkdir(parents=True,exist_ok=True)
        self.path=directory/'sessions.sqlite3'
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, body TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)')

    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            with db: yield db
        finally: db.close()

    def create(self,title):
        session={'id':'S'+uuid4().hex,'title':title[:80] or '新会话','state':'new','material_ids':[],'messages':[],'reports':[],'traces':[],'revision':0,'updated_at':datetime.now(timezone.utc).isoformat()}
        with self._connect() as db: db.execute('INSERT INTO sessions(id,body) VALUES(?,?)',(session['id'],json.dumps(session,ensure_ascii=False)))
        return session

    def get(self,sid):
        with self._connect() as db: row=db.execute('SELECT body FROM sessions WHERE id=?',(sid,)).fetchone()
        if not row: raise KeyError('会话不存在')
        return json.loads(row[0])

    def save(self,session):
        revision=session['revision']
        session['revision']=revision+1; session['updated_at']=datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cursor=db.execute('UPDATE sessions SET body=?,revision=? WHERE id=? AND revision=?',(json.dumps(session,ensure_ascii=False),revision+1,session['id'],revision))
            if cursor.rowcount!=1: raise ValueError('会话已变化，请重新提交')

    def list(self):
        with self._connect() as db: rows=db.execute('SELECT body FROM sessions').fetchall()
        sessions=[json.loads(r[0]) for r in rows]
        return sorted([{'id':s['id'],'title':s['title'],'state':s['state'],'updated_at':s['updated_at']} for s in sessions],key=lambda s:s['updated_at'],reverse=True)

    def delete(self,sid):
        with self._connect() as db:
            if db.execute('DELETE FROM sessions WHERE id=?',(sid,)).rowcount!=1: raise KeyError('会话不存在')
