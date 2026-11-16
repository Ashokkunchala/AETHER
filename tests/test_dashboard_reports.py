"""Execute the dashboard's real date/report helper without a browser dependency."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'app/static/life-reports.js'


def run_js(source, timezone='Asia/Kolkata'):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is needed for JavaScript helper execution')
    prelude = "const assert=require('node:assert/strict');global.window={};require(process.argv[1]);const R=window.AetherReports;\n"
    result = subprocess.run([node, '-e', prelude + source, str(HELPER)],
                            env={**os.environ, 'TZ': timezone}, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(('timezone', 'instant', 'expected'), [
    ('Asia/Kolkata', '2026-10-31T20:00:00Z', '2026-11-01'),
    ('America/Los_Angeles', '2026-11-01T02:00:00Z', '2026-10-31'),
    ('America/Los_Angeles', '2026-03-08T10:00:00Z', '2026-03-08'),
])
def test_local_date_not_utc(timezone, instant, expected):
    run_js(f"assert.equal(R.localDate(new Date('{instant}')), '{expected}');assert(R.timezone());", timezone)


def test_month_boundaries_validation_and_separate_totals():
    run_js("""
(async()=>{
 const urls=[];const api=async p=>{urls.push(p);return {totals:[]}};
 await R.monthReport(api,'2028-02');await R.monthReport(api,'2026-12');
 assert.equal(urls[0],'/api/life/reports/expenses?start_date=2028-02-01&end_date=2028-02-29');
 assert(urls[1].endsWith('end_date=2026-12-31'));
 for(const bad of ['2026-00','2026-13','2026-1','0026-01','2026-11&x=y'])await assert.rejects(()=>R.monthReport(api,bad));
 assert.equal(urls.length,2);
 assert.equal(R.amounts({totals:[{currency:'INR',amount:'100.25'},{currency:'USD',amount:'2.00'}],partial:true,invalid_records_skipped:1}),'INR 100.25 · USD 2.00 (PARTIAL) (invalid records skipped)');
 assert.equal(R.amounts({totals:[]}), 'No expenses');
})().catch(e=>{console.error(e);process.exitCode=1});
""")


def test_report_rendering_safe_text_and_partial_empty_state():
    run_js("""
(async()=>{
 const element=()=>({children:[],textContent:'',append(...xs){this.children.push(...xs)},replaceChildren(){this.children=[]}});
 const elements={todayTasks:element(),overdueCount:element()};
 global.document={getElementById:id=>elements[id],createElement:element};let url;
 const report={counts:{overdue:2},date:'2026-11-01',timezone:'Asia/Kolkata',top_priorities:[{title:'<img src=x onerror=alert(1)>',priority:1,status:'open'}],partial_scan:true,invalid_records_skipped:1};
 await R.renderToday(async p=>{url=p;return report});
 assert(url.includes('/reports/today?timezone='));assert.equal(elements.overdueCount.textContent,'2+');
 assert(elements.todayTasks.children[0].textContent.includes('Partial scan.'));
 assert(elements.todayTasks.children[0].textContent.includes('Invalid records skipped.'));
 assert.equal(elements.todayTasks.children[1].children[0].children[0].textContent,report.top_priorities[0].title);
 report.top_priorities=[];await R.renderToday(async()=>report);
 assert(elements.todayTasks.children.at(-1).textContent.includes('Future tasks remain on the task board.'));
})().catch(e=>{console.error(e);process.exitCode=1});
""")


def test_dashboard_uses_helper_and_preserves_legacy_board():
    html = (ROOT / 'app/static/life-manager.html').read_text()
    assert html.index('src="/static/life-reports.js"') < html.index('const $=')
    assert 'new Date().toISOString().slice(0,' not in html
    assert 'await AetherReports.renderToday(api)' in html
    assert 'monthReport:AetherReports.monthReport' in html
    assert 'await expensePanel.load' in html or 'return expensePanel.load()' in html
    assert 'monthReport(api,month)' in (ROOT / 'app/static/expense-panel.js').read_text()
    assert 'Before today in browser timezone' in html
    assert 'data-done' in html and 'data-postpone' in html and 'data-delete-task' in html
