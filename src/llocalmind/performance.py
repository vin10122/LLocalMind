"""Small local latency reports without prompts, pixels, keys or model paths."""
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime,timezone
from .app_paths import data_root


def memory_snapshot(pid=None):
    """Read OS counters; page faults include both soft and hard faults."""
    result={}
    try:
        if os.name=='nt':
            import ctypes as c
            from ctypes import wintypes as w
            class Memory(c.Structure):
                _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(name,c.c_ulonglong) for name in
                    ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
            memory=Memory();memory.length=c.sizeof(memory)
            if c.windll.kernel32.GlobalMemoryStatusEx(c.byref(memory)):
                result.update(total_ram_bytes=memory.total,available_ram_bytes=memory.available)
            if type(pid) is int:
                class Counters(c.Structure):
                    _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(name,c.c_size_t) for name in
                        ('peak','working','paged_peak','paged','nonpaged_peak','nonpaged','pagefile','pagefile_peak','private')]
                kernel=c.windll.kernel32
                kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]
                kernel.OpenProcess.restype=w.HANDLE
                kernel.CloseHandle.argtypes=[w.HANDLE]
                handle=kernel.OpenProcess(0x410,False,pid)
                if handle:
                    try:
                        counters=Counters();counters.cb=c.sizeof(counters)
                        fn=c.windll.psapi.GetProcessMemoryInfo
                        fn.argtypes=[w.HANDLE,c.POINTER(Counters),w.DWORD]
                        if fn(handle,c.byref(counters),counters.cb):
                            result.update(process_rss_bytes=counters.working,process_peak_rss_bytes=counters.peak,
                                          process_private_bytes=counters.private,page_faults=counters.faults)
                    finally:kernel.CloseHandle(handle)
        elif Path('/proc/meminfo').is_file():
            values={line.split(':')[0]:int(line.split()[1])*1024
                    for line in Path('/proc/meminfo').read_text().splitlines() if line.split()[1].isdigit()}
            result.update(total_ram_bytes=values['MemTotal'],available_ram_bytes=values.get('MemAvailable',values['MemFree']))
            if type(pid) is int:
                for line in Path(f'/proc/{pid}/status').read_text().splitlines():
                    name=line.split(':')[0]
                    if name in ('VmRSS','VmHWM'):
                        result['process_rss_bytes' if name=='VmRSS' else 'process_peak_rss_bytes']=int(line.split()[1])*1024
    except (OSError,ValueError,KeyError,AttributeError):pass
    return result


def record(phase,engine,values):
    folder=data_root()/'logs'
    temporary=None
    try:
        folder.mkdir(parents=True,exist_ok=True)
        filename=folder/('performance-'+phase+'.json')
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=folder,delete=False) as out:
            temporary=Path(out.name)
            json.dump(dict(engine=engine,timestamp=datetime.now(timezone.utc).isoformat(),**values),out,indent=2,allow_nan=False)
        os.replace(temporary,filename)
        temporary=None
    except (OSError,ValueError,TypeError):
        # Diagnostic persistence must never break a completed response.
        pass
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
