/* AETHER read-only shared-brain client. No browser storage or HTML rendering. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let socket = null, epoch = 0, busy = false, ready = false, answer = null, connecting = false;
  const status = text => { $('status').textContent = text; };
  function controls() {
    $('connect').disabled = connecting || Boolean(socket);
    $('disconnect').disabled = !socket && !connecting;
    $('send').disabled = !ready || busy;
    $('cancel').disabled = !ready || !busy;
  }
  function append(role, text) {
    const el = document.createElement('article');
    el.dataset.role = role;
    el.textContent = (role === 'user' ? 'You: ' : 'AETHER: ') + text;
    $('messages').append(el);
    el.scrollIntoView({block: 'nearest'});
    return el;
  }
  function disconnect() {
    epoch++;
    const old = socket;
    socket = null; ready = false; busy = false; connecting = false; answer = null;
    if (old) old.close();
    $('token').value = '';
    controls(); status('Disconnected. A new connection starts a new chat session.');
  }
  $('connect').addEventListener('click', async () => {
    const token = $('token').value.trim();
    if (!token || connecting || socket) return;
    const attempt = ++epoch;
    connecting = true; controls(); status('Connecting to the read-only profile...');
    try {
      const response = await fetch('/api/ws-ticket?profile=personal-readonly', {
        method: 'POST', headers: {Authorization: 'Bearer ' + token}, cache: 'no-store',
        signal: AbortSignal.timeout(10000)
      });
      if (!response.ok) throw new Error(response.status === 404 ? 'Start the enhanced backend to use this preview.' : 'Connection refused (' + response.status + '). Check your token and backend.');
      const data = await response.json();
      if (attempt !== epoch) return;
      const url = new URL('/ws', location.href);
      url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      url.searchParams.set('ticket', data.ticket);
      const current = new WebSocket(url);
      socket = current;
      const handshakeTimer = setTimeout(() => {
        if (attempt === epoch && connecting) { disconnect(); status('Handshake timed out. Check the enhanced backend.'); }
      }, 10000);
      $('token').value = '';
      current.onmessage = event => {
        if (attempt !== epoch || socket !== current) return;
        let message;
        try { message = JSON.parse(event.data); } catch (_) { disconnect(); status('Invalid backend response. Disconnected.'); return; }
        if (message.type === 'ready') {
          if (message.profile !== 'personal-readonly') { disconnect(); status('Wrong capability profile. Disconnected without sending a chat.'); return; }
          clearTimeout(handshakeTimer);
          connecting = false;
          ready = Boolean(message.configured);
          if (ready) append('assistant', 'New read-only session. Earlier messages, if shown, are not part of this session.');
          status(ready ? 'Connected: read-only personal data. No actions enabled.' : 'Connected, but no AI provider is configured. Disconnect and configure one first.');
        } else if (message.type === 'text_delta') {
          if (!answer) answer = append('assistant', '');
          answer.textContent += message.text || '';
        } else if (message.type === 'confirm') {
          // This capability set cannot write. Never offer a broad approval button.
          current.send(JSON.stringify({type: 'approve', id: message.id, approved: false}));
          $('approval').hidden = false;
          status('Unexpected action request rejected. Read-only profile only.');
        } else if (message.type === 'tool_start') {
          status('Reading saved data: ' + message.tool);
        } else if (message.type === 'done') {
          if (!answer && message.text) append('assistant', message.text);
          busy = false; answer = null; status('Turn complete. Read-only profile.');
        } else if (message.type === 'error') {
          busy = false; answer = null; append('assistant', message.error || 'Request failed.'); status('Turn failed. Nothing was changed.');
        }
        controls();
      };
      current.onerror = () => { if (attempt === epoch) status('Connection error. Check the enhanced backend.'); };
      current.onclose = () => {
        clearTimeout(handshakeTimer);
        if (attempt !== epoch) return;
        socket = null; ready = false; busy = false; connecting = false; answer = null;
        controls(); status('Disconnected or access revoked. Reconnect to start a new session.');
      };
    } catch (error) {
      if (attempt !== epoch) return;
      connecting = false; socket = null; controls(); status(error.message);
    }
  });
  $('disconnect').addEventListener('click', disconnect);
  $('composer').addEventListener('submit', event => {
    event.preventDefault();
    const text = $('message').value.trim();
    if (!text || busy || !ready || socket?.readyState !== WebSocket.OPEN) return;
    append('user', text); $('message').value = ''; busy = true; answer = null;
    socket.send(JSON.stringify({type: 'chat', message: text})); controls(); status('Thinking...');
  });
  $('cancel').addEventListener('click', () => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: 'cancel'}));
    // Close to discard all late events and guarantee a fresh conversation next time.
    disconnect(); status('Turn cancelled and connection closed. Already-sent provider data cannot be recalled.');
  });
  window.addEventListener('pagehide', disconnect);
  controls();
})();
