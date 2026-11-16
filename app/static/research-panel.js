/* Source research only. Never render outside text as HTML or claim verified prices. */
(() => {
  'use strict';
  function render(target, data) {
    target.replaceChildren(); target.classList.remove('hidden');
    const notice = document.createElement('p'); notice.textContent = data.notice;
    target.append(notice);
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
        body.append(link, host, snippet); card.append(body); target.append(card);
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
