"""Request-local cancellation with an atomic final save."""
from contextvars import ContextVar
from contextlib import contextmanager
from threading import RLock
from time import monotonic
class TaskCancelled(RuntimeError):pass
active_task=ContextVar('active_task',default=None)
class TaskToken:
    def __init__(self):
        self.lock=RLock();self.status='pending';self.aborts=[];self.cleanups=[];self.updated=monotonic()
    def check(self):
        if self.status=='cancelled':raise TaskCancelled('已停止本次生成')
    def own(self,cleanup):
        with self.lock:
            immediate=self.status=='cancelled'
            if not immediate:self.cleanups.append(cleanup)
        if immediate:cleanup()
    @contextmanager
    def abortable(self,abort):
        with self.lock:self.check();self.aborts.append(abort)
        try:yield
        finally:
            with self.lock:
                if abort in self.aborts:self.aborts.remove(abort)
            self.check()
    def cancel(self):
        with self.lock:
            if self.status=='completed':return self.status
            self.status='cancelled';self.updated=monotonic()
            callbacks=self.aborts+self.cleanups;self.cleanups=[]
        for callback in callbacks:
            try:callback()
            except Exception:pass
        return 'cancelled'
    def commit(self,save):
        with self.lock:
            self.check();save();self.status='completed';self.cleanups=[];self.updated=monotonic()
class TaskRegistry:
    def __init__(self):self.lock=RLock();self.tokens={};self.deleted_sessions=set()
    def get(self,sid,request_id):
        with self.lock:
            for key,token in list(self.tokens.items()):
                if token.status in {'completed','cancelled'} and monotonic()-token.updated>3600:del self.tokens[key]
            token=self.tokens.setdefault((sid,request_id),TaskToken())
            deleted=sid in self.deleted_sessions
        if deleted:token.cancel()
        return token
    def cancel_session(self,sid):
        with self.lock:
            self.deleted_sessions.add(sid)
            tokens=[token for (session_id,_),token in self.tokens.items() if session_id==sid]
        for token in tokens:token.cancel()
    @contextmanager
    def scope(self,sid,request_id):
        token=self.get(sid,request_id)
        with token.lock:
            token.check()
            if token.status=='completed':raise TaskCancelled('本次任务已完成，请勿重复提交')
            token.status='running'
        binding=active_task.set(token)
        try:yield token
        finally:active_task.reset(binding)
def check_cancelled():
    token=active_task.get()
    if token:token.check()
@contextmanager
def abortable_client(client):
    token=active_task.get()
    if token:
        with token.abortable(client.close):yield
    else:yield
def commit(save):
    token=active_task.get()
    if token:token.commit(save)
    else:save()
