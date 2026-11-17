"""Generate a custom local dashboard from exact supplied data, not live telemetry.

No JavaScript, model-generated HTML, remote assets, hosting or filesystem overwrite.
"""
from __future__ import annotations

import html
import json
import math
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path


def text(value, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Bounded nonempty text required, no controls.')
    return value.strip()


def validate(spec):
    if not isinstance(spec, dict) or set(spec) - {'title', 'subtitle', 'source_note', 'as_of', 'metrics', 'chart', 'table'}:
        raise ValueError('Use the documented dashboard data schema, no HTML/scripts/URLs.')
    out = {k: text(spec[k], 300 if k != 'title' else 100) for k in ('title', 'source_note', 'as_of')}
    out['subtitle'] = text(spec.get('subtitle', 'AETHER data dashboard'), 200)
    metrics = spec.get('metrics', [])
    if not isinstance(metrics, list) or len(metrics) > 8:
        raise ValueError('At most8 metrics.')
    out['metrics'] = []
    for metric in metrics:
        if not isinstance(metric, dict) or set(metric) != {'label', 'value', 'note'}:
            raise ValueError('Metric requires label, value and note text.')
        out['metrics'].append({k: text(metric[k], 100) for k in metric})
    chart = spec.get('chart')
    out['chart'] = None
    if chart is not None:
        if not isinstance(chart, dict) or set(chart) != {'title', 'unit', 'points'} or not isinstance(chart['points'], list) or not 1 <= len(chart['points']) <= 16:
            raise ValueError('Bar chart needs title, unit and1-16 label/value points.')
        points = []
        for p in chart['points']:
            if not isinstance(p, dict) or set(p) != {'label', 'value'} or type(p['value']) not in (int, float) or not math.isfinite(p['value']) or not 0 <= p['value'] <= 1e12:
                raise ValueError('Bar values must be finite nonnegative supplied numbers, no inferred totals.')
            points.append({'label': text(p['label'], 80), 'value': p['value']})
        out['chart'] = {'title': text(chart['title'], 100), 'unit': text(chart['unit'], 40), 'points': points}
    table = spec.get('table')
    out['table'] = None
    if table is not None:
        if not isinstance(table, dict) or set(table) != {'title', 'columns', 'rows'} or not isinstance(table['columns'], list) or not 1 <= len(table['columns']) <= 6 or not isinstance(table['rows'], list) or len(table['rows']) > 100:
            raise ValueError('Table needs1-6 columns and at most100 rows.')
        columns = [text(c, 80) for c in table['columns']]
        rows = []
        for row in table['rows']:
            if not isinstance(row, list) or len(row) != len(columns):
                raise ValueError('Each row must match the column count.')
            rows.append([text(cell, 300) for cell in row])
        out['table'] = {'title': text(table['title'], 100), 'columns': columns, 'rows': rows}
    if not metrics and chart is None and table is None:
        raise ValueError('Provide a metric, chart or table, not an empty dashboard.')
    return out


CSS = '''*{box-sizing:border-box}body{margin:0;background:#f4efec;color:#251f21;font:16px/1.55 system-ui,sans-serif}main{max-width:1120px;margin:40px auto;padding:36px;background:white;border-radius:20px}header{border-bottom:1px solid #eae9ea;padding-bottom:24px}h1,h2{font-family:Georgia,serif;font-weight:400;line-height:1.18;letter-spacing:-.025em}h1{font-size:40px;margin:10px 0 16px}h2{font-size:27px;margin:0 0 20px}.eyebrow{font-size:12px;letter-spacing:.13em;font-weight:600;color:#585254}.sub,.note{color:#585254}.metadata{display:flex;gap:24px;flex-wrap:wrap;font-size:13px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:28px 0}.metric,.panel{border:1px solid #eae9ea;border-radius:12px;padding:20px;min-width:0}.metric:only-child{grid-column:1/-1}.value{font-size:32px;font-weight:600;color:#326f60;margin:8px 0;line-height:1.2}.label{font-size:14px;font-weight:600}.note{font-size:13px;margin-top:8px}.panel{margin-top:24px}.barrow{display:grid;grid-template-columns:minmax(100px,1fr) 3fr minmax(65px,1fr);gap:14px;align-items:center;margin:17px 0}.track{height:16px;background:#f4efec;border-radius:4px;overflow:hidden}.bar{height:100%;background:#73a89a}.number{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left;font-size:14px}th,td{padding:14px 12px;vertical-align:top;border-bottom:1px solid #eae9ea;overflow-wrap:anywhere}th{font-size:12px;color:#585254}footer{margin-top:30px;border-top:1px solid #eae9ea;padding-top:18px;color:#585254;font-size:13px}h1,h2,p,.label,.value,.note,.barrow,.metadata{overflow-wrap:anywhere}.empty{color:#585254}@media(max-width:600px){main{margin:0;padding:22px 16px;border-radius:0}h1{font-size:30px}.metrics{grid-template-columns:1fr 1fr;gap:10px}.metric{padding:14px}.value{font-size:25px}.panel{padding:16px}.barrow{grid-template-columns:1fr auto;gap:6px}.track{grid-column:1/-1;grid-row:auto}.number{grid-column:2;grid-row:auto}.tablewrap{overflow:visible}table,tbody,tr,td{display:block}thead{display:none}tr{border-bottom:1px solid #eae9ea;padding:12px 0}td{border:0;padding:6px 0}td:before{content:attr(data-label);display:block;font-size:12px;font-weight:600;color:#585254;margin-bottom:3px}}'''


def render_dashboard(spec):
    data = validate(spec)
    e = lambda v: html.escape(str(v), quote=True)
    metrics = ''.join('<div class="metric"><div class="label">'+e(m['label'])+'</div><div class="value">'+e(m['value'])+'</div><div class="note">'+e(m['note'])+'</div></div>' for m in data['metrics'])
    content = '<section class="metrics" aria-label="Supplied metrics">'+metrics+'</section>' if metrics else ''
    chart = data['chart']
    if chart:
        maximum = max(p['value'] for p in chart['points']) or 1
        rows = ''.join('<div class="barrow"><div>'+e(p['label'])+'</div><div class="track" aria-hidden="true"><div class="bar" style="width:'+format(p['value'] / maximum * 100, '.5f')+'%"></div></div><div class="number">'+e(format(p['value'], ',g'))+' '+e(chart['unit'])+'</div></div>' for p in chart['points'])
        content += '<section class="panel"><h2>'+e(chart['title'])+'</h2><p class="note">Zero-based bars; scale maximum '+e(format(max(p['value'] for p in chart['points']), ',g'))+' '+e(chart['unit'])+'. Values are supplied, not measured by AETHER.</p>'+rows+'</section>'
    table = data['table']
    if table:
        heads = ''.join('<th scope="col">'+e(c)+'</th>' for c in table['columns'])
        rows = ''.join('<tr>'+''.join('<td data-label="'+e(c)+'">'+e(v)+'</td>' for c, v in zip(table['columns'], row, strict=True))+'</tr>' for row in table['rows'])
        content += '<section class="panel"><h2>'+e(table['title'])+'</h2><div class="tablewrap"><table><thead><tr>'+heads+'</tr></thead><tbody>'+rows+'</tbody></table></div>'+('' if rows else '<p class="empty">No rows supplied.</p>')+'</section>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src \'none\'; base-uri \'none\'; form-action \'none\'"><title>'+e(data['title'])+' | AETHER</title><style>'+CSS+'</style></head><body><main><header><div class="eyebrow">AETHER / CUSTOM DATA VIEW</div><h1>'+e(data['title'])+'</h1><p class="sub">'+e(data['subtitle'])+'</p><div class="metadata"><span>Data as of: '+e(data['as_of'])+'</span><span>Source: '+e(data['source_note'])+'</span></div></header>'+content+'<footer>Local static dashboard. No live connection, tracking, external assets or automatic refresh. Supplied values and source labels have not been independently verified. Generated '+datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')+'.</footer></main></body></html>'


def create_dashboard(spec, name):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}', name):
        raise ValueError('Choose a lowercase dashboard name using letters, digits and hyphens.')
    document = render_dashboard(spec)
    root = Path(os.environ.get('AETHER_DASHBOARD_DIR', str(Path.home() / '.jarvis' / 'dashboards'))).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    output = root / (name+'-'+secrets.token_hex(8)+'.html')
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(document)
    return {'created': True, 'path': str(output.absolute()), 'url': output.absolute().as_uri(), 'bytes': len(document.encode()), 'notice': 'New local static HTML only, not published/uploaded or visually verified. Open it locally and inspect desktop/mobile layout before sharing. No live data or charts inferred.'}


def preview_dashboard(spec, name):
    data = validate(spec)
    return {'title': data['title'], 'name': name, 'metrics': len(data['metrics']), 'chart_points': len(data['chart']['points']) if data['chart'] else 0, 'table_rows': len(data['table']['rows']) if data['table'] else 0, 'notice': 'Creates one NEW local HTML in the configured dashboard directory; exact supplied content remains private on this machine. No overwrite, script, network, hosting or app launch. Review source/date/values before saving.'}


def register_dashboard_tools(registry):
    from jarvis.tools.registry import Risk, Tool
    registry.register(Tool(name='create_custom_dashboard', description='Create one custom local HTML dashboard from supplied title/source/as-of, text metric cards, optional nonnegative bar chart and table. No live data, arbitrary HTML/JS, hosting or auto-open. Review required.', parameters={'type':'object','properties':{'name':{'type':'string'},'spec':{'type':'object','description':'title/source_note/as_of required; subtitle optional; metrics:[{label,value,note}]; chart:{title,unit,points:[{label,value:number}]}; table:{title,columns:[text],rows:[[text]]}. No HTML/scripts.'}},'required':['name','spec'],'additionalProperties':False},handler=create_dashboard,confirmation_preview=preview_dashboard,risk=Risk.MEDIUM,category='dashboard',requires_confirmation=True,never_auto_approve=True,allow_always=False,allow_auto_approve=False))


def main():
    import argparse
    import sys
    parser=argparse.ArgumentParser(description='Create an owner-reviewed static AETHER dashboard from a JSON spec')
    parser.add_argument('--spec',required=True);parser.add_argument('--name',required=True)
    args=parser.parse_args()
    source=Path(args.spec)
    if not source.is_file() or source.stat().st_size>262144:
        raise SystemExit('Use one existing JSON spec up to256KiB.')
    data=json.loads(source.read_text(encoding='utf-8'))
    print(json.dumps(preview_dashboard(data,args.name),indent=2))
    if not sys.stdin.isatty() or input('Type CREATE LOCAL DASHBOARD after reviewing the exact spec file: ')!='CREATE LOCAL DASHBOARD':
        raise SystemExit('Not approved. No dashboard created.')
    if _stopped():
        raise SystemExit('Emergency stop active; no dashboard created.')
    print(json.dumps(create_dashboard(data,args.name),indent=2))


def _stopped():
    from jarvis.security import SecurityStore
    return SecurityStore().stopped()


if __name__=='__main__':
    main()
