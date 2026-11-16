/* Private previews and reviewed downloads. No HTML rendering of document text. */
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  get('documentLibrary').addEventListener('click', async () => {
    const button = get('documentLibrary'), list = get('documentLibraryList'), status = get('documentLibraryStatus');
    button.disabled = true; list.replaceChildren(); get('documentPreview').classList.add('hidden');
    try {
      const data = await api('/api/documents/library'); status.textContent = (data.partial ? 'Partial listing. ' : '') + data.notice;
      for (const record of data.items || []) {
        const row = document.createElement('div'); row.className = 'item';
        const body = document.createElement('div'); body.className = 'item-main';
        const title = document.createElement('div'); title.className = 'item-title'; title.textContent = record.name;
        const detail = document.createElement('div'); detail.className = 'item-meta'; detail.textContent = record.path + ' · ' + record.modified_at;
        const preview = document.createElement('button'); preview.type = 'button'; preview.textContent = 'Preview text';
        preview.addEventListener('click', async () => {
          preview.disabled = true; const target = get('documentPreview'); target.classList.remove('hidden'); target.textContent = 'Reading authorized text...';
          try {
            const data = await api('/api/documents/preview', {method:'POST', body:JSON.stringify({path:record.path})});
            target.textContent = (data.partial ? 'PARTIAL PREVIEW\n' : '') + data.notice + '\n\n' + data.text;
          } catch (error) { target.textContent = error.message; }
          finally { preview.disabled = false; }
        });
        body.append(title, detail, preview); row.append(body); list.append(row);
      }
      if (!data.items.length) status.textContent = 'No supported files found. ' + data.notice;
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
