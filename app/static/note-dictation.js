/* Optional own-voice dictation. Never saves a note or starts without a click. */
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const start = get('noteVoiceStart'), stop = get('noteVoiceStop'), add = get('noteVoiceAppend');
  const draft = get('noteVoiceDraft'), status = get('noteVoiceStatus');
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let current = null, timer = null;
  function say(text) { status.textContent = text; }
  function finish(recognition) {
    if (current !== recognition) return;
    clearTimeout(timer); timer = null; current = null;
    start.disabled = false; stop.disabled = true; add.disabled = false; draft.readOnly = false;
  }
  function cancel() {
    if (!current) return;
    const recognition = current; finish(recognition); recognition.abort();
    say('Microphone stopped. Review the unsaved draft. Late results are ignored.');
  }
  function endCapture() {
    if (!current) return;
    const recognition = current; recognition.stop(); stop.disabled = true;
    clearTimeout(timer); timer = setTimeout(() => { if (current === recognition) cancel(); }, 3000);
    say('Stopping microphone and waiting for final text. Nothing is saved.');
  }
  if (!Recognition) {
    start.disabled = true;
    say('Speech recognition is unavailable in this browser. Type or paste a transcript instead.');
  }
  start.addEventListener('click', () => {
    if (current || !Recognition) return;
    if (!get('noteVoiceConsent').checked) { say('Confirm this is your own voice and review the privacy notice first.'); return; }
    if (!window.isSecureContext) { say('Dictation needs localhost or HTTPS. Type or paste instead.'); return; }
    const recognition = new Recognition();
    const local = get('noteVoiceMode').value === 'local';
    if (local && !('processLocally' in recognition)) {
      say('This browser cannot require on-device recognition. Nothing started. Type/paste or explicitly choose browser-service mode.'); return;
    }
    if ('processLocally' in recognition) recognition.processLocally = local;
    recognition.lang = get('noteVoiceLanguage').value;
    recognition.continuous = true; recognition.interimResults = false; recognition.maxAlternatives = 1;
    current = recognition; draft.readOnly = true; start.disabled = true; stop.disabled = false; add.disabled = true;
    const base = draft.value;
    recognition.onresult = event => {
      if (current !== recognition) return;
      const pieces = [];
      // Rebuild from the complete final-result list so repeated result events cannot duplicate text.
      for (let i=0; i<event.results.length; i++) if (event.results[i].isFinal) pieces.push(event.results[i][0].transcript);
      const text = [base, pieces.join(' ')].filter(Boolean).join('\n');
      if (text.length > 12000) { draft.value = text.slice(0,12000); cancel(); say('Draft reached 12000 characters. Capture stopped; review the truncated text.'); return; }
      draft.value = text;
    };
    recognition.onerror = event => {
      if (current !== recognition) return;
      finish(recognition); recognition.abort();
      say('Dictation stopped (' + String(event.error || 'error') + '). Nothing saved. Local mode may need an installed language pack; no automatic cloud fallback.');
    };
    recognition.onend = () => {
      if (current !== recognition) return;
      finish(recognition); say('Microphone stopped. Review the draft, append it, then use Save note. Nothing saved automatically.');
    };
    try {
      recognition.start();
      say(local ? 'Starting on-device dictation. Stops after 2 minutes. Nothing saved.' : 'Starting browser-service dictation. Audio may leave this device for browser-provider processing. Stops after 2 minutes.');
      timer = setTimeout(endCapture, 120000);
    } catch (_) { finish(recognition); recognition.abort(); say('Could not start dictation. Check browser permissions or type/paste instead.'); }
  });
  stop.addEventListener('click', endCapture);
  for (const id of ['noteVoiceConsent','noteVoiceMode','noteVoiceLanguage']) get(id).addEventListener('change', cancel);
  add.addEventListener('click', () => {
    if (current) return;
    const body = get('noteForm').elements.body;
    const text = [body.value, draft.value.trim()].filter(Boolean).join('\n');
    if (!draft.value.trim()) { say('The draft is empty.'); return; }
    if (text.length > 12000) { say('Combined note exceeds 12000 characters. Shorten it before appending; nothing changed.'); return; }
    body.value = text; draft.value = ''; get('noteForm').elements.kind.value = 'voice';
    say('Appended to the unsaved note. Review title, type and text, then use Save note.');
  });
  get('noteVoiceClear').addEventListener('click', () => { cancel(); draft.value = ''; say('Unsaved dictation draft cleared.'); });
  get('disconnectBtn').addEventListener('click', cancel);
  get('noteForm').addEventListener('submit', cancel, true);
  document.addEventListener('visibilitychange', () => { if (document.hidden) cancel(); });
  window.addEventListener('pagehide', cancel);
  const view = get('view-notes');
  new MutationObserver(() => { if (!view.classList.contains('active')) cancel(); }).observe(view, {attributes:true, attributeFilter:['class']});
})();
