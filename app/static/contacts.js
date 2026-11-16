/* Explicit Contacts reads only. Uses the existing life-manager tab connection. */
(() => {
  'use strict';
  const status = document.getElementById('contactsStatus');
  const results = document.getElementById('contactsResults');
  const connect = document.getElementById('contactsConnect');
  const form = document.getElementById('contactsSearch');
  let busy = false;
  connect.addEventListener('click', async () => {
    if (busy) return;
    if (!window.confirm('Allow AETHER to request read-only Google Contacts access? This reconnects the same Google integration used for email and calendar. Check the account selected on Google. Nothing will be messaged or edited.')) return;
    try {
      const data = await api('/api/integrations/google/connect?include_contacts=true');
      const url = new URL(data.authorization_url);
      if (url.origin !== 'https://accounts.google.com' || url.pathname !== '/o/oauth2/v2/auth') throw Error('Unexpected authorization destination.');
      window.location.assign(url.href);
    } catch (error) { status.textContent = error.message; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    const query = form.elements.q.value.trim(); if (!query) return;
    busy = true; connect.disabled = true; form.querySelector('button').disabled = true;
    results.replaceChildren(); status.textContent = 'Warming Google search cache, then searching. No contact will be changed or messaged...';
    try {
      const data = await api('/api/contacts/search?q=' + encodeURIComponent(query) + '&limit=20');
      for (const person of data.items || []) {
        const el = document.createElement('div'); el.className = 'item';
        const text = document.createElement('div'); text.className = 'item-main';
        const title = document.createElement('div'); title.className = 'item-title';
        title.textContent = person.names.join(' / ') || '(No saved name)';
        const detail = document.createElement('div'); detail.className = 'item-meta';
        detail.textContent = [...person.emails, ...person.phones, ...person.organizations].join(' · ') || 'No email or phone returned';
        text.append(title, detail); el.append(text); results.append(el);
      }
      status.textContent = (data.items.length ? 'Returned ' + data.items.length + ' contacts. ' : 'No prefix matches returned. ') + data.notice;
    } catch (error) { status.textContent = error.message; }
    finally { busy = false; connect.disabled = false; form.querySelector('button').disabled = false; }
  });
})();
