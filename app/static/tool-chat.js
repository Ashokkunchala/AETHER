/* AETHER narrow-profile client. No browser storage or HTML rendering. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let socket = null, epoch = 0, busy = false, ready = false, answer = null, connecting = false;
  let activeProfile = 'personal-readonly', pendingApproval = null, approvalTimer = null;
  const status = text => { $('status').textContent = text; };
  function controls() {
    $('profile').disabled = connecting || Boolean(socket);
    $('connect').disabled = connecting || Boolean(socket);
    $('disconnect').disabled = !socket && !connecting;
    $('send').disabled = !ready || busy;
    $('cancel').disabled = !ready || !busy;
  }
  function append(role, text) {
    const el = document.createElement('article');
    el.dataset.role = role;
    el.textContent = (role === 'user' ? 'You: ' : 'AETHER: ') + text;
    $('messages').append(el); el.scrollIntoView({block: 'nearest'});
    return el;
  }
  function clearApproval() {
    clearTimeout(approvalTimer); approvalTimer = null; pendingApproval = null;
    $('approval').hidden = true; $('approvalDetails').textContent = '';
  }
  function decide(approved) {
    const id = pendingApproval; clearApproval();
    if (id && socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: 'approve', id, approved}));
    status(approved ? 'Approval sent. Waiting for the save result...' : 'Action rejected.');
  }
  function disconnect() {
    clearApproval(); epoch++;
    const old = socket;
    socket = null; ready = false; busy = false; connecting = false; answer = null;
    if (old) old.close();
    $('token').value = '';
    controls(); status('Disconnected. A new connection starts a new chat session. Check saved records before retrying any approved action.');
  }
  $('connect').addEventListener('click', async () => {
    const token = $('token').value.trim();
    if (!token || connecting || socket) return;
    const attempt = ++epoch; activeProfile = $('profile').value;
    connecting = true; controls(); status('Connecting to ' + activeProfile + '...');
    try {
      const response = await fetch('/api/ws-ticket?profile=' + encodeURIComponent(activeProfile), {
        method: 'POST', headers: {Authorization: 'Bearer ' + token}, cache: 'no-store',
        signal: AbortSignal.timeout(10000)
      });
      if (!response.ok) throw new Error(response.status === 404 ? 'Start the enhanced backend to use this preview.' : 'Connection refused (' + response.status + '). Check your token and backend.');
      const data = await response.json();
      if (attempt !== epoch) return;
      const url = new URL('/ws', location.href);
      url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      url.searchParams.set('ticket', data.ticket);
      const current = new WebSocket(url); socket = current;
      const handshakeTimer = setTimeout(() => {
        if (attempt === epoch && connecting) { disconnect(); status('Handshake timed out. Check the enhanced backend.'); }
      }, 10000);
      $('token').value = '';
      current.onmessage = event => {
        if (attempt !== epoch || socket !== current) return;
        let message;
        try { message = JSON.parse(event.data); } catch (_) { disconnect(); status('Invalid backend response. Disconnected.'); return; }
        if (message.type === 'ready') {
          if (message.profile !== activeProfile) { disconnect(); status('Wrong capability profile. Disconnected without sending a chat.'); return; }
          clearTimeout(handshakeTimer); connecting = false; ready = Boolean(message.configured);
          if (ready) append('assistant', 'New ' + activeProfile + ' session. Earlier messages, if shown, are not part of this session.');
          status(ready ? 'Connected: ' + activeProfile + (activeProfile === 'personal-local' ? '. Each local write needs approval.' : '. No actions enabled.') : 'Connected, but no AI provider is configured. Disconnect and configure one first.');
        } else if (message.type === 'text_delta') {
          if (!answer) answer = append('assistant', '');
          answer.textContent += message.text || '';
        } else if (message.type === 'confirm') {
          if (activeProfile !== 'personal-local' || !message.args?._preview || message.category !== 'personal_local') {
            current.send(JSON.stringify({type: 'approve', id: message.id, approved: false}));
            status('Unexpected action request rejected.');
          } else {
            clearApproval(); pendingApproval = message.id;
            $('approvalDetails').textContent = JSON.stringify({tool: message.tool, ...message.args._preview}, null, 2);
            $('approval').hidden = false;
            $('approval').scrollIntoView({block: 'start'});
            approvalTimer = setTimeout(() => { decide(false); status('Approval expired. Pending action rejected.'); }, 60000);
            status('Waiting for your review of this local action.');
          }
        } else if (message.type === 'tool_start') {
          status('Tool: ' + message.tool);
        } else if (message.type === 'tool_cancelled' || message.type === 'tool_error') {
          clearApproval(); status('Action not completed: ' + (message.error || message.tool));
        } else if (message.type === 'done') {
          if (!answer && message.text) append('assistant', message.text);
          clearApproval(); busy = false; answer = null; status('Turn complete. ' + activeProfile + '.');
        } else if (message.type === 'error') {
          clearApproval(); busy = false; answer = null;
          append('assistant', message.error || 'Request failed.');
          status('Turn failed. If you approved an action, check saved records before retrying.');
        }
        controls();
      };
      current.onerror = () => { if (attempt === epoch) status('Connection error. Check saved records before retrying any approved action.'); };
      current.onclose = () => {
        clearTimeout(handshakeTimer);
        if (attempt !== epoch) return;
        clearApproval(); socket = null; ready = false; busy = false; connecting = false; answer = null;
        controls(); status('Disconnected or access revoked. Check saved records before retrying any approved action.');
      };
    } catch (error) {
      if (attempt !== epoch) return;
      connecting = false; socket = null; controls(); status(error.message);
    }
  });
  $('approve').addEventListener('click', () => decide(true));
  $('reject').addEventListener('click', () => decide(false));
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
    disconnect(); status('Turn cancelled and connection closed. Committed writes cannot be undone; provider data cannot be recalled.');
  });
  window.addEventListener('pagehide', disconnect);
  controls();
})();
