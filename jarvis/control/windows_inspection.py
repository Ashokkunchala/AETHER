"""Bounded local inspection. No services, startup entries or network links changed."""
from __future__ import annotations

import os
import platform
from datetime import datetime, timezone
from pathlib import Path


def _base(kind):
    return {'kind':kind,'as_of':datetime.now(timezone.utc).isoformat(),'changes_made':False,
            'partial':False,'unavailable_sources':[],'items':[]}


def _label(value):
    if not isinstance(value,str):return 'unknown'
    return ''.join(c for c in value if ord(c)>=32 and ord(c)!=127)[:200]


def service_inventory():
    result=_base('windows_service_inventory')
    result['limits']='Snapshot only, not service health/complete inventory or change approval. No binary paths, command lines, usernames or descriptions returned. No start/stop/install/configure/elevation. Access denied/disappearing/unsupported services remain partial/unknown.'
    if platform.system()!='Windows':
        return {**result,'success':False,'partial':True,'unavailable_sources':['Windows service API unavailable on this OS']}
    import psutil
    try:
        iterator=iter(psutil.win_service_iter())
        for index,service in enumerate(iterator):
            if index>=300:result['partial']=True;break
            try:
                name=_label(service.name());display=_label(service.display_name())
                state=service.status();start=service.start_type()
                known_states={'running','paused','start_pending','pause_pending','continue_pending','stop_pending','stopped'}
                result['items'].append({'name':name,'display_name':display,
                    'state':state if state in known_states else 'unknown',
                    'start_type':start if start in {'automatic','manual','disabled'} else 'unknown'})
            except Exception:
                result['partial']=True;result['unavailable_sources'].append('A service detail could not be read')
    except Exception:
        result['partial']=True;result['unavailable_sources'].append('Service enumeration unavailable or interrupted')
    result['unavailable_sources']=sorted(set(result['unavailable_sources']))
    return {**result,'success':not result['partial'] or bool(result['items'])}


def _registry_names():
    import winreg
    items=[];sources=[];partial=False
    for hive_label,hive in [('current_user',winreg.HKEY_CURRENT_USER),('local_machine',winreg.HKEY_LOCAL_MACHINE)]:
        for key_name in ['Run','RunOnce']:
            for view_label,view in [('32bit',winreg.KEY_WOW64_32KEY),('64bit',winreg.KEY_WOW64_64KEY)]:
                source=f'{hive_label}/{key_name}/{view_label}'
                try:
                    with winreg.OpenKey(hive,'Software\\Microsoft\\Windows\\CurrentVersion\\'+key_name,0,winreg.KEY_READ|view) as key:
                        count=winreg.QueryInfoKey(key)[1]
                        for index in range(min(count,100)):
                            name,_,_=winreg.EnumValue(key,index)
                            items.append({'source':source,'entry_name':_label(name),'target_omitted':True})
                        limited=count>100
                        sources.append({'source':source,'state':'partial_limit' if limited else 'queried'})
                        partial=partial or limited
                except FileNotFoundError:sources.append({'source':source,'state':'absent'})
                except Exception:
                    sources.append({'source':source,'state':'unavailable'});partial=True
    return items,sources,partial


def _folder_names():
    items=[];sources=[];partial=False
    for variable in ['APPDATA','PROGRAMDATA']:
        source=variable+'/Startup'
        try:
            root=os.environ.get(variable)
            if not root or root.startswith(('\\\\','//')):raise ValueError('Missing or network known-folder environment anchor')
            folder=Path(root)/'Microsoft'/'Windows'/'Start Menu'/'Programs'/'Startup'
            if not folder.is_absolute() or folder.is_symlink() or folder.resolve()!=folder:raise ValueError('Noncanonical startup directory')
            if not folder.exists():
                sources.append({'source':source,'state':'absent'});continue
            with os.scandir(folder) as entries:
                limited=False
                for index,entry in enumerate(entries):
                    if index>=100:limited=True;break
                    # Never follow/open .lnk, scripts, symlinks or shortcut targets.
                    items.append({'source':source,'entry_name':_label(entry.name),'target_omitted':True})
            sources.append({'source':source,'state':'partial_limit' if limited else 'queried'})
            partial=partial or limited
        except Exception:
            sources.append({'source':source,'state':'unavailable'});partial=True
    return items,sources,partial


def startup_inventory():
    result=_base('windows_startup_inventory')
    result['limits']='Scoped snapshot of Run/RunOnce names in current-user/local-machine32/64 views and conventional APPDATA/PROGRAMDATA Startup folder entry names, at most100 per source. Views may overlap; no unique app count. Values/commands/shortcut contents/targets are deliberately omitted. Presence is not effective enabled/executed state, safety, publisher approval or deletion advice. Not services, scheduled tasks, policies, other users or all autostart locations. No file/registry change or target execution. Environment/OS and folder mapping must be trusted.'
    if platform.system()!='Windows':
        return {**result,'success':False,'partial':True,'unavailable_sources':['Windows registry/known folders unavailable on this OS'],'sources':[]}
    sources=[]
    for reader,label in [(_registry_names,'registry'),(_folder_names,'startup_folders')]:
        try:
            items,states,partial=reader();result['items'].extend(items);sources.extend(states)
            result['partial']=result['partial'] or partial
        except Exception:
            result['partial']=True;result['unavailable_sources'].append(label+' unavailable')
    return {**result,'sources':sources,'success':not result['partial'] or bool(result['items'])}


def network_link_inventory():
    result=_base('network_link_inventory');result['internet_reachability_verified']=False
    result['limits']='Local NIC link flags only, not internet/DNS/TLS/Wi-Fi association/backend reachability, a speed test or continuous monitoring. No packets/probes, address/SSID/connection inventory or configuration changes. Speed0/negative/nonfinite means unknown; speed is reported link capacity, not measured throughput.'
    import math

    import psutil
    try:
        stats=psutil.net_if_stats()
        for index,(name,info) in enumerate(stats.items()):
            if index>=100:result['partial']=True;break
            speed=info.speed;mtu=info.mtu
            result['items'].append({'name':_label(name),'link_up':info.isup if type(info.isup) is bool else None,
                'reported_link_mbps':speed if type(speed) in (int,float) and math.isfinite(speed) and speed>0 else None,
                'mtu_bytes':mtu if type(mtu) is int and mtu>0 else None})
    except Exception:
        result['partial']=True;result['unavailable_sources'].append('Local interface stats unavailable or interrupted')
    return {**result,'success':not result['partial'] or bool(result['items'])}


def register_windows_inspection_tools(registry):
    from jarvis.tools.registry import Risk, Tool
    for name,handler,scope in [
        ('windows_service_inventory',service_inventory,'Read bounded Windows service names/display names/status/start type. No command lines or mutation.'),
        ('windows_startup_inventory',startup_inventory,'Read bounded Run/RunOnce and Startup entry names only, not targets/commands. No enable/disable/delete.'),
        ('network_link_inventory',network_link_inventory,'Read local interface link flags/capacity/MTU only. No active probes, addresses or internet-health claim.')]:
        registry.register(Tool(name=name,description=scope+' Fresh approval required. Snapshot may be partial; no real-device acceptance.',
            parameters={'type':'object','properties':{},'additionalProperties':False},handler=handler,
            confirmation_preview=lambda scope=scope:{'effect':scope,'privacy':'Local system names/status may be private and may enter the configured assistant/provider context. Approve only this scoped read and intended disclosure. No ongoing monitor.'},
            risk=Risk.LOW,category='system',requires_confirmation=True,never_auto_approve=True,allow_always=False,allow_auto_approve=False))
