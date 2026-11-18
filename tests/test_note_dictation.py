"""Run dictation state-machine JS with a fake recognizer, never a microphone."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'app/static/note-dictation.js'
PRELUDE = r"""
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const elements={};
class Element extends EventTarget{constructor(){super();this.value='';this.checked=false;this.disabled=false;this.readOnly=false;this.textContent='';this.classList={contains:()=>true};}click(){this.dispatchEvent(new Event('click'));}change(){this.dispatchEvent(new Event('change'));}}
for(const id of ['noteVoiceStart','noteVoiceStop','noteVoiceAppend','noteVoiceClear','noteVoiceDraft','noteVoiceStatus','noteVoiceConsent','noteVoiceMode','noteVoiceLanguage','disconnectBtn','noteForm','view-notes'])elements[id]=new Element();
elements.noteForm.elements={body:new Element(),kind:new Element()};elements.noteVoiceMode.value='local';elements.noteVoiceLanguage.value='en-IN';
global.document=new EventTarget();document.getElementById=id=>elements[id];document.hidden=false;
global.window=new EventTarget();window.isSecureContext=true;global.MutationObserver=class{constructor(cb){global.onViewChange=cb;}observe(){}};
let ticks=new Map(),next=1;global.setTimeout=(cb,ms)=>{const key=next++;ticks.set(key,{cb,ms});return key};global.clearTimeout=key=>ticks.delete(key);
class Recognition{constructor(){this.processLocally=false;global.rec=this;}start(){this.started=true;}stop(){this.stopped=true;this.onend?.();}abort(){this.aborted=true;}result(text){this.onresult?.({results:[Object.assign([{transcript:text}],{isFinal:true})]});}}
window.SpeechRecognition=Recognition;
const e=elements;const load=()=>vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));const consent=()=>e.noteVoiceConsent.checked=true;
"""


def run(source):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node needed for dictation JavaScript tests')
    result = subprocess.run([node, '-e', PRELUDE + source, str(SCRIPT)], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_start_without_consent_and_secure_context():
    run("""load();e.noteVoiceStart.click();assert.equal(typeof rec,'undefined');consent();window.isSecureContext=false;e.noteVoiceStart.click();assert.equal(typeof rec,'undefined');""")


def test_unsupported_browser_and_local_mode_never_falls_back():
    run("window.SpeechRecognition=undefined;load();assert(e.noteVoiceStart.disabled);assert(e.noteVoiceStatus.textContent.includes('unavailable'));")
    run("""window.SpeechRecognition=class{start(){throw Error('Should not start')}};load();consent();e.noteVoiceStart.click();assert(e.noteVoiceStatus.textContent.includes('cannot require on-device'));""")


def test_explicit_browser_service_and_language():
    run("load();consent();e.noteVoiceMode.value='browser';e.noteVoiceLanguage.value='te-IN';e.noteVoiceStart.click();assert(rec.started);assert.equal(rec.processLocally,false);assert.equal(rec.lang,'te-IN');assert(e.noteVoiceStatus.textContent.includes('Audio may leave'));")


def test_final_results_deduplicated_and_reviewed_append_only():
    run(r"""load();consent();e.noteVoiceDraft.value='Earlier';e.noteVoiceStart.click();assert(rec.processLocally);assert(e.noteVoiceDraft.readOnly);rec.result('<script>literal text</script>');rec.result('<script>literal text</script>');assert.equal(e.noteVoiceDraft.value,'Earlier\n<script>literal text</script>');assert.equal(e.noteForm.elements.body.value,'');e.noteVoiceStop.click();assert(!e.noteVoiceDraft.readOnly);e.noteVoiceAppend.click();assert.equal(e.noteForm.elements.body.value,'Earlier\n<script>literal text</script>');assert.equal(e.noteVoiceDraft.value,'');assert.equal(e.noteForm.elements.kind.value,'voice');""")


@pytest.mark.parametrize('action', [
    "e.disconnectBtn.click()", "document.hidden=true;document.dispatchEvent(new Event('visibilitychange'))",
    "e['view-notes'].classList.contains=()=>false;onViewChange()", "window.dispatchEvent(new Event('pagehide'))",
    "e.noteVoiceMode.change()", "e.noteVoiceConsent.change()", "e.noteVoiceLanguage.change()",
])
def test_cancel_ignores_late_results(action):
    run("load();consent();e.noteVoiceStart.click();" + action + ";assert(rec.aborted);rec.result('LATE');assert.equal(e.noteVoiceDraft.value,'');assert(!e.noteVoiceStart.disabled);")


def test_two_minute_bound_and_no_auto_restart():
    run("load();consent();e.noteVoiceStart.click();const tick=[...ticks.values()].find(x=>x.ms===120000);assert(tick);tick.cb();assert(rec.stopped);assert(!e.noteVoiceStart.disabled);")


def test_truncation_and_append_overflow_do_not_save():
    run("load();consent();e.noteVoiceStart.click();rec.result('x'.repeat(12001));assert(rec.aborted);assert.equal(e.noteVoiceDraft.value.length,12000);e.noteForm.elements.body.value='original';e.noteVoiceAppend.click();assert.equal(e.noteForm.elements.body.value,'original');assert(e.noteVoiceStatus.textContent.includes('exceeds'));")


def test_error_and_clear_and_no_network_or_storage():
    run("load();consent();e.noteVoiceStart.click();rec.onerror({error:'not-allowed'});assert(rec.aborted);assert(!e.noteVoiceStart.disabled);e.noteVoiceDraft.value='draft';e.noteVoiceClear.click();assert.equal(e.noteVoiceDraft.value,'');")
    source = SCRIPT.read_text()
    assert 'fetch(' not in source and 'localStorage' not in source and 'sessionStorage' not in source
    assert '.submit(' not in source and '.requestSubmit(' not in source
