/* Private previews and reviewed downloads. No HTML rendering of document text. */
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  let records = [];
  function renderLibrary() {
    const list = get('documentLibraryList'); list.replaceChildren();
    const grouped = get('documentGrouping').value === 'type';
    const items = grouped ? [...records].sort((a,b) => a.name.split('.').pop().localeCompare(b.name.split('.').pop()) || a.name.localeCompare(b.name)) : records;
    let previous = '';
    for (const record of items) {
      const kind = record.name.split('.').pop().toUpperCase();
      if (grouped && kind !== previous) { const heading = document.createElement('h3'); heading.textContent = kind; list.append(heading); previous = kind; }
      const row = document.createElement('div'); row.className = 'item';
      const body = document.createElement('div'); body.className = 'item-main';
      const title = document.createElement('div'); title.className = 'item-title'; title.textContent = record.name;
      const detail = document.createElement('div'); detail.className = 'item-meta'; detail.textContent = record.path + ' · ' + record.modified_at;
      body.append(title, detail);
      for (const mode of ['preview', 'summary']) {
        const button = document.createElement('button'); button.type = 'button';
        button.textContent = mode === 'preview' ? 'Preview text' : 'Summarize locally (exact extracts)';
        button.addEventListener('click', async () => {
          button.disabled = true; const target = get('documentPreview'); target.classList.remove('hidden'); target.textContent = 'Reading authorized text locally...';
          try {
            const data = await api('/api/documents/' + mode, {method:'POST', body:JSON.stringify({path:record.path})});
            if (mode === 'preview') target.textContent = (data.partial ? 'PARTIAL PREVIEW\n' : '') + data.notice + '\n\n' + data.text;
            else target.textContent = (data.partial_source || data.candidate_scan_partial ? 'PARTIAL SOURCE / SCAN\n' : '') + data.notice + '\n\n' + data.source_notice + '\n\n' + (data.excerpts.length ? data.excerpts.map((x,i)=>'['+(i+1)+'] Extracted characters '+x.start+'-'+x.end+(x.excerpt_truncated ? ' (passage truncated)' : '')+'\n'+x.text).join('\n\n') : 'No suitable passages. Open the preview; the document may be short, scanned or missing extractable text.');
          } catch (error) { target.textContent = error.message; }
          finally { button.disabled = false; }
        });
        body.append(button);
      }
      row.append(body); list.append(row);
    }
  }
  get('documentGrouping').addEventListener('change', renderLibrary);
  get('documentLibrary').addEventListener('click', async () => {
    const button = get('documentLibrary'), status = get('documentLibraryStatus');
    button.disabled = true; records = []; renderLibrary(); get('documentPreview').classList.add('hidden');
    try {
      const data = await api('/api/documents/library'); status.textContent = (data.partial ? 'Partial listing. ' : '') + data.notice;
      records = data.items || []; renderLibrary();
      if (!records.length) status.textContent = 'No supported files found. ' + data.notice;
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
  get('documentCreate').addEventListener('submit', async event => {
    event.preventDefault(); const form = event.target, button = form.querySelector('button'), status = get('documentCreateStatus');
    if (button.disabled) return;
    if (!token) { status.textContent = 'Connect your device token first.'; return; }
    button.disabled = true; status.textContent = 'Preparing the reviewed download...';
    try {
      const data = Object.fromEntries(new FormData(form));
      const response = await fetch('/api/documents/download', {method:'POST', headers:{'Content-Type':'application/json',...auth()}, body:JSON.stringify(data), cache:'no-store'});
      if (!response.ok) { const error = await response.json().catch(()=>({})); throw Error(typeof error.detail === 'string' ? error.detail : 'Download request failed. Check the fields.'); }
      const blob = await response.blob(), url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url; link.download = data.filename + '.' + data.format; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      status.textContent = 'Download handed to your browser. Check its download list. No server file was saved, shared or overwritten.';
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  });
})();
