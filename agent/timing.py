"""Content-free, request-correlated timing events for local diagnostics."""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4
import json
import logging

_context=ContextVar('timing_context',default=None)
_lock=Lock()

def _logger():
 logger=logging.getLogger('jobmirror.timing')
 with _lock:
  if not logger.handlers:
   folder=Path(__file__).resolve().parent.parent/'logs'
   folder.mkdir(parents=True,exist_ok=True)
   handler=RotatingFileHandler(folder/'agent-timing.jsonl',maxBytes=5*1024*1024,backupCount=3,encoding='utf-8')
   handler.setFormatter(logging.Formatter('%(message)s'))
   logger.addHandler(handler)
   logger.setLevel(logging.INFO)
   logger.propagate=False
 return logger

def event(stage,event_name,**fields):
 # Only internal labels, counts, IDs and exception class names reach this logger.
 from datetime import datetime,timezone
 try:
  payload={'time':datetime.now(timezone.utc).isoformat(),**(_context.get() or {}),'stage':stage,'event':event_name,**fields}
  _logger().info(json.dumps(payload,ensure_ascii=False))
 except Exception:
  pass  # Diagnostic storage failure must never break a user's request.

@contextmanager
def span(stage,**fields):
 start=perf_counter()
 event(stage,'start',**fields)
 status='ok';error_type=None
 try: yield
 except BaseException as exc:
  error_type=type(exc).__name__
  status='cancelled' if error_type=='TaskCancelled' else 'error'
  raise
 finally:
  event(stage,'end',**fields,status=status,elapsed_ms=round((perf_counter()-start)*1000,3),**({'error_type':error_type} if error_type else {}))

def measured(stage,fn,/,*args,**kwargs):
 with span(stage): return fn(*args,**kwargs)

def timed(stage):
 def decorate(fn):
  @wraps(fn)
  def wrapped(*args,**kwargs):
   with span(stage): return fn(*args,**kwargs)
  return wrapped
 return decorate

def timed_turn(fn):
 @wraps(fn)
 def wrapped(self,sid,*args,**kwargs):
  from .tasks import active_task
  token=active_task.get()
  binding=_context.set({'session_id':sid,'request_id':getattr(token,'request_id',None) or uuid4().hex})
  try:
   with span('turn_total'): return fn(self,sid,*args,**kwargs)
  finally: _context.reset(binding)
 return wrapped
