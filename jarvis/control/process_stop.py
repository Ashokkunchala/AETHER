"""Exact selected-process stop. No name search, recursive stop or escalation."""
from __future__ import annotations

import math
import os
from pathlib import Path

from jarvis.control.process import CRITICAL_PROCESSES


def _resolve(pid, expected_create_time, expected_executable):
    import psutil
    if type(pid) is not int or pid<=4 or pid==os.getpid():raise ValueError('Select a non-system PID, not this AETHER process.')
    if type(expected_create_time) not in (int,float) or not math.isfinite(expected_create_time) or expected_create_time<=0:
        raise ValueError('Exact finite positive process create_time is required.')
    if not isinstance(expected_executable,str) or not expected_executable or len(expected_executable)>2000 or expected_executable.startswith(('\\\\','//')) or not Path(expected_executable).is_absolute():
        raise ValueError('Exact absolute non-network executable path is required.')
    proc=psutil.Process(pid)
    # No substring matching or process enumeration selects a target.
    if proc.create_time()!=expected_create_time or proc.exe()!=expected_executable:
        raise ValueError('Process identity changed or does not match. Select again; no stop requested.')
    if proc.name().lower() in CRITICAL_PROCESSES:
        raise ValueError('Critical process is protected.')
    if pid in {p.pid for p in psutil.Process(os.getpid()).parents()}:
        raise ValueError('AETHER ancestor processes are protected.')
    if not proc.is_running():raise ValueError('Selected process is no longer running.')
    return proc


def preview_process_stop(pid,expected_create_time,expected_executable):
    proc=_resolve(pid,expected_create_time,expected_executable)
    return {'success':True,'pid':pid,'create_time':expected_create_time,'executable':expected_executable,'name':proc.name(),
            'effect':'Terminate only this process. Unsaved work may be lost. Windows termination is forceful, not graceful app-close. Wait up to5seconds to verify exit; no kill retry, child/tree stop or escalation.',
            'limits':'Exit does not prove work saved, children exited, app UI closed or service stopped. Local OS/process query permissions required.'}


def stop_exact_process(pid,expected_create_time,expected_executable):
    import psutil
    proc=_resolve(pid,expected_create_time,expected_executable)
    # psutil additionally checks identity before terminate; OS races are not a sandbox.
    proc.terminate()
    try:
        code=proc.wait(timeout=5)
    except psutil.TimeoutExpired:
        return {'success':False,'pid':pid,'termination_requested':True,'exit_verified':False,'error':'Exit not verified within5seconds. No force retry or escalation performed.'}
    return {'success':True,'pid':pid,'create_time':expected_create_time,'executable':expected_executable,
            'termination_requested':True,'exit_verified':True,'exit_code':code,'children_stopped_verified':False,'work_saved_verified':False}
