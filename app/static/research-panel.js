/* Source research only. Never render outside text as HTML or claim verified prices. */
(() => {
  'use strict';
  function renderComparison(target, data) {
    target.replaceChildren();
    const notice = document.createElement('p'); notice.textContent = data.notice; target.append(notice);
    const grid = document.createElement('div'); grid.style.display = 'grid'; grid.style.gridTemplateColumns = 'repeat(auto-fit,minmax(min(260px,100%),1fr))'; grid.style.gap = '12px';
    for (const page of data.pages || []) {
      const card = document.createElement('article'); card.className = 'card'; card.style.minWidth = '0'; card.style.gridColumn = 'auto'; card.style.overflowWrap = 'anywhere';
      const title = document.createElement('h3'); title.textContent = page.title || 'Source unavailable'; card.append(title);
      let safe; try { safe = new URL(page.url || page.requested_url); } catch (_) { safe = null; }
      const link = document.createElement(safe && safe.protocol === 'https:' && !safe.username && !safe.password ? 'a' : 'span'); if (link.tagName === 'A') link.href = safe.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.style.color = 'var(--cyan)'; link.textContent = page.url || page.requested_url; card.append(link);
      const state = document.createElement('p'); state.textContent = page.page_read ? 'Extracted at ' + page.read_at + (page.partial ? ' · PARTIAL TEXT' : '') + ' · Claims/quotes not verified' : page.notice; card.append(state);
      for (const [label, snippets] of Object.entries(page.evidence || {})) {
        const heading = document.createElement('h4'); heading.textContent = label; card.append(heading);
        for (const text of snippets.length ? snippets : ['Not found in extracted text. Check the original page; absence is not established.']) {
          const quote = document.createElement('p'); quote.textContent = text; card.append(quote);
        }
      }
      if (page.text) { const details = document.createElement('details'), summary = document.createElement('summary'), text = document.createElement('pre'); summary.textContent = 'Show bounded extracted source text'; text.style.whiteSpace = 'pre-wrap'; text.style.overflowWrap = 'anywhere'; text.textContent = page.text; details.append(summary,text); card.append(details); }
      grid.append(card);
    }
    target.append(grid);
  }
  function render(target, data) {
    target.replaceChildren(); target.classList.remove('hidden');
    const notice = document.createElement('p'); notice.textContent = data.notice;
    target.append(notice);
    const selected = new Set(), selectable = new Set(); let comparing = false;
    const privacy = document.createElement('p'); privacy.textContent = 'Select up to 3 HTTPS pages to compare their extracted public source text. Only selected URLs are requested, without cookies or login. Do not select private or signed links. This does not verify a final price, stock, itinerary or terms.';
    const compare = document.createElement('button'); compare.type = 'button'; compare.textContent = 'Read and compare selected public pages'; compare.disabled = true;
    const output = document.createElement('div'); output.setAttribute('role','status');
    target.append(privacy,compare,output);
    compare.addEventListener('click', async () => {
      if (!selected.size || compare.disabled || comparing) return;
      comparing = true;
      compare.disabled = true; output.textContent = 'Reading selected public sources, not booking or purchasing...';
      try { renderComparison(output, await api('/api/research/pages/compare', {method:'POST',body:JSON.stringify({urls:[...selected]})})); }
      catch (error) { output.textContent = 'Source comparison failed: ' + error.message; }
      finally { comparing = false; compare.disabled = !selected.size; }
    });
    for (const group of data.groups || []) {
      const heading = document.createElement('h3'); heading.textContent = group.topic;
      const details = document.createElement('p'); details.textContent = group.notice;
      target.append(heading, details);
      for (const source of group.sources || []) {
        let url;
        try { url = new URL(source.url); } catch (_) { continue; }
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) continue;
        const card = document.createElement('div'); card.className = 'item';
        const body = document.createElement('div'); body.className = 'item-main';
        const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.style.color = 'var(--cyan)'; link.style.overflowWrap = 'anywhere';
        link.textContent = source.title || url.hostname;
        const host = document.createElement('p'); host.textContent = url.hostname + ' · Search snippet, page unverified';
        const snippet = document.createElement('p'); snippet.textContent = source.snippet;
        body.append(link, host, snippet);
        if (url.protocol === 'https:' && !selectable.has(url.href)) {
          selectable.add(url.href);
          const label = document.createElement('label'), checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.style.width = 'auto';
          label.append(checkbox, document.createTextNode(' Include this public page in comparison'));
          checkbox.addEventListener('change', () => {
            if (checkbox.checked && !selected.has(url.href) && selected.size >= 3) { checkbox.checked = false; output.textContent = 'Choose at most 3 distinct source pages.'; return; }
            if (checkbox.checked) selected.add(url.href); else selected.delete(url.href);
            compare.disabled = comparing || !selected.size;
          });
          body.append(label);
        }
        card.append(body); target.append(card);
      }
    }
  }
  function bind(formId, targetId, endpoint, fields) {
    const form = document.getElementById(formId), target = document.getElementById(targetId);
    let busy = false;
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (busy) return;
      const input = Object.fromEntries(new FormData(form)), body = fields(input);
      busy = true; const button = form.querySelector('button'); button.disabled = true;
      target.classList.remove('hidden'); target.textContent = 'Searching public sources. No booking or purchase will be made...';
      try { render(target, await api(endpoint, {method:'POST', body: JSON.stringify(body)})); }
      catch (error) { target.textContent = 'Research failed: ' + error.message + '. No conclusions about prices or availability can be drawn.'; }
      finally { busy = false; button.disabled = false; }
    });
  }
  bind('travelForm', 'travelResult', '/api/research/travel', d => ({origin:d.from, destination:d.to, travel_date:d.date || null, preferences:d.prefs || ''}));
  bind('shopForm', 'shopResult', '/api/research/shopping', d => ({query:d.query, budget:d.budget || '', preferences:d.prefs || '', market:d.market}));
})();
