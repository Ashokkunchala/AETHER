/* Local calendar dates and read-only life-manager reports. No saved record writes. */
window.AetherReports = (() => {
  'use strict';
  const get = id => document.getElementById(id);
  function localDate(now = new Date()) {
    return [now.getFullYear(), String(now.getMonth()+1).padStart(2,'0'), String(now.getDate()).padStart(2,'0')].join('-');
  }
  function timezone() { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; }
  async function monthReport(api, month) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month) || Number(month.slice(0,4)) < 1000) throw Error('Choose a valid month (year 1000 or later).');
    const [year, number] = month.split('-').map(Number), last = new Date(year, number, 0).getDate();
    return api('/api/life/reports/expenses?start_date=' + month + '-01&end_date=' + month + '-' + last);
  }
  function amounts(report) {
    const totals = report.totals.map(row => row.currency + ' ' + row.amount).join(' · ') || 'No expenses';
    return totals + (report.partial ? ' (PARTIAL)' : '') + (report.invalid_records_skipped ? ' (invalid records skipped)' : '');
  }
  async function renderToday(api) {
    const data = await api('/api/life/reports/today?timezone=' + encodeURIComponent(timezone()));
    get('overdueCount').textContent = String(data.counts.overdue) + (data.partial_scan ? '+' : '');
    const target = get('todayTasks'); target.replaceChildren();
    const notice = document.createElement('p'); notice.className = 'muted';
    notice.textContent = data.date + ' · ' + data.timezone + ' · Local records only. Drafts are not booked events.' + (data.partial_scan ? ' Partial scan.' : '') + (data.invalid_records_skipped ? ' Invalid records skipped.' : '');
    target.append(notice);
    for (const task of data.top_priorities) {
      const row = document.createElement('div'); row.className = 'item';
      const main = document.createElement('div'); main.className = 'item-main';
      const title = document.createElement('div'); title.className = 'item-title'; title.textContent = task.title;
      const meta = document.createElement('div'); meta.className = 'item-meta';
      meta.textContent = 'P' + task.priority + ' · ' + task.status + ' · ' + (task.due_local || 'No due date');
      main.append(title,meta); row.append(main); target.append(row);
    }
    if (!data.top_priorities.length) { const empty = document.createElement('p'); empty.textContent = 'No overdue, due-today or undated priorities in the bounded saved-task scan. Future tasks remain on the task board.'; target.append(empty); }
  }
  return {localDate, timezone, monthReport, amounts, renderToday};
})();
