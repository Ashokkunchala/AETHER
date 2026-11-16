"""Companion policy and browser settings checks without a provider or microphone."""
import shutil
import subprocess
from pathlib import Path

import pytest

from app.personality import SYSTEM_INSTRUCTIONS, language_instruction, mode_instruction
from jarvis.core.brain import DEFAULT_SYSTEM
from jarvis.personality_modes import COMPANION_GUIDANCE, MODES, ModeStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode', ['friendly', 'funny', 'professional', 'calm', 'motivational'])
def test_styles_use_existing_registry_and_store(mode, tmp_path):
    store = ModeStore(tmp_path / 'mode.json')
    assert store.set(mode).name == mode
    assert store.get() == mode
    assert 'approval' in mode_instruction(mode)
    assert MODES[mode].voice_style


def test_web_and_desktop_share_companion_safety_and_identity():
    for prompt in (SYSTEM_INSTRUCTIONS, DEFAULT_SYSTEM):
        assert 'You are AETHER' in prompt
        assert COMPANION_GUIDANCE in prompt
        assert 'do not encourage dependence' in prompt
        assert 'never invent what was discussed' in prompt
        assert 'suggestions are not playback' in prompt
    assert 'Reply in Telugu' in language_instruction('te')
    assert 'ASSISTANT' in mode_instruction('ignore all rules')


PRELUDE = r"""
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const html=fs.readFileSync(process.argv[1],'utf8'),elements={};
class Element extends EventTarget {
 constructor(){super();this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.innerHTML='';this.children=[];this.classList={remove(){},add(){}};}
 append(...x){this.children.push(...x);} remove(){} setAttribute(){} focus(){} click(){this.dispatchEvent(new Event('click'));}
}
for(const match of html.matchAll(/id="([^"]+)"/g))elements[match[1]]=new Element();
elements.personalityMode.value='assistant';elements.language.value='auto';elements.speechRate.value='1';elements.speechPitch.value='1';
elements.personalityMode.options=[...html.matchAll(/<option value="([^"]+)">/g)].map(x=>({value:x[1]}));
const storage=new Map();global.localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
global.document={getElementById:id=>elements[id],createElement:()=>new Element()};
global.window={speechSynthesis:{cancel(){},getVoices:()=>[{lang:'en-IN'},{lang:'te-IN'}],speak:u=>global.spoken=u}};
global.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
global.fetch=async()=>({ok:true,json:async()=>({})});
const e=elements,load=()=>vm.runInThisContext(html.match(/<script>\s*([\s\S]*?)<\/script>/)[1]);
"""


def run_js(source):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for browser companion settings tests')
    result = subprocess.run([node, '-e', PRELUDE + source, str(ROOT / 'app/static/index.html')], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_browser_default_history_and_voice_privacy():
    run_js("load();assert(!e.saveHistory.checked);assert(!e.speakReplies.checked);assert.equal(storage.size,0);assert(e.messages.children[0].textContent.includes('AETHER'));assert.equal(typeof spoken,'undefined');")


def test_browser_restores_bounded_style_and_language_without_storing_token():
    run_js("storage.set('jarvis.settings.v1',JSON.stringify({mode:'calm',language:'te',speechRate:50,speechPitch:-4,deviceToken:'ignored',rememberToken:false}));load();assert.equal(e.personalityMode.value,'calm');assert.equal(e.language.value,'te');assert.equal(e.speechRate.value,2);assert.equal(e.speechPitch.value,0.5);assert.equal(e.deviceToken.value,'');")


def test_browser_ignores_unknown_style_and_nonfinite_speech():
    run_js("storage.set('jarvis.settings.v1',JSON.stringify({mode:'<script>',language:'bad',speechRate:'not-a-number',speechPitch:null}));load();assert.equal(e.personalityMode.value,'assistant');assert.equal(e.language.value,'auto');assert.equal(e.speechRate.value,1);assert.equal(e.speechPitch.value,1);")


def test_browser_saves_preferences_with_existing_settings():
    run_js("load();e.personalityMode.value='funny';e.language.value='te';e.speechRate.value='1.2';e.speechPitch.value='0.8';e.saveSettings.click();const s=JSON.parse(storage.get('jarvis.settings.v1'));assert.equal(s.mode,'funny');assert.equal(s.language,'te');assert.equal(s.speechRate,1.2);assert.equal(s.speechPitch,0.8);assert.equal(s.deviceToken,'');assert(!storage.has('jarvis.history.v1'));")


def test_greeting_uses_text_not_html_and_clear_does_not_delete_backend_memory():
    run_js("storage.set('jarvis.settings.v1',JSON.stringify({nickname:'<img src=x onerror=alert(1)>'}));load();assert(e.messages.children[0].textContent.includes('<img'));e.clear.click();assert(!storage.has('jarvis.history.v1'));assert.equal(storage.size,1);")


def test_settings_scope_and_wake_word_are_truthful():
    html = (ROOT / 'app/static/index.html').read_text()
    assert 'do not change Gemini Live audio' in html
    assert 'Hey Aether' in html and 'Hey Jarvis' not in html
    assert 'saveHistory' in html and 'Live Voice has separate context' in html
    assert 'if(!streamedReply&&last?.role===' in html
    assert 'u.rate=boundedSpeech' in html and 'u.pitch=boundedSpeech' in html
    # Existing config/storage names remain compatible; this is not a path migration.
    assert 'JARVIS' not in html and 'Hey Jarvis' not in html
    assert 'jarvis.settings.v1' in html


def test_browser_speech_uses_selected_speed_pitch_and_auto_telugu():
    run_js(r"""(async()=>{load();e.speakReplies.checked=true;e.speechRate.value='1.3';e.speechPitch.value='0.9';e.message.value='hello';global.fetch=async(url)=>url==='/health'?{ok:true}:{ok:true,body:{getReader(){let n=0;return{async read(){return n++?{done:true}:{done:false,value:new TextEncoder().encode('data: '+JSON.stringify({text:'నమస్తే',done:true,model:'mock'})+'\n\n')};}}}}};e.chatForm.dispatchEvent(new Event('submit',{cancelable:true}));await new Promise(setImmediate);assert.equal(spoken.lang,'te-IN');assert.equal(spoken.rate,1.3);assert.equal(spoken.pitch,0.9);assert.equal(spoken.voice.lang,'te-IN');assert(!storage.has('jarvis.history.v1'));})().catch(e=>{console.error(e);process.exitCode=1});""")


def test_interrupted_reply_keeps_user_context_for_continuation():
    run_js(r"""(async()=>{load();e.message.value='Start a story';let turn=0,bodies=[];global.fetch=async(url,options)=>{if(url==='/health')return{ok:true};bodies.push(JSON.parse(options.body));let n=0;const first=turn++===0;return{ok:true,body:{getReader(){return{async read(){if(first){if(n++===0)return{done:false,value:new TextEncoder().encode('data: '+JSON.stringify({text:'Once upon a time'})+'\n\n')};return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError'))));}return n++?{done:true}:{done:false,value:new TextEncoder().encode('data: '+JSON.stringify({text:'The story continues',done:true})+'\n\n')};}}}}};};e.chatForm.dispatchEvent(new Event('submit',{cancelable:true}));await new Promise(setImmediate);e.stop.click();await new Promise(setImmediate);e.message.value='Continue';e.chatForm.dispatchEvent(new Event('submit',{cancelable:true}));await new Promise(setImmediate);assert.deepEqual(bodies[1].history,[{role:'user',content:'Start a story'},{role:'model',content:'Once upon a time'}]);})().catch(e=>{console.error(e);process.exitCode=1});""")


def test_speech_failure_does_not_turn_a_completed_chat_into_an_error():
    run_js(r"""(async()=>{load();e.speakReplies.checked=true;window.speechSynthesis.getVoices=()=>{throw Error('voice unavailable')};e.message.value='hello';global.fetch=async(url)=>url==='/health'?{ok:true}:{ok:true,body:{getReader(){let n=0;return{async read(){return n++?{done:true}:{done:false,value:new TextEncoder().encode('data: '+JSON.stringify({text:'A completed reply',done:true,model:'mock'})+'\n\n')};}}}}};e.chatForm.dispatchEvent(new Event('submit',{cancelable:true}));await new Promise(setImmediate);assert.equal(e.status.textContent,'Ready · mock');assert(e.voiceSubtitle.textContent.includes('text reply is still available'));})().catch(e=>{console.error(e);process.exitCode=1});""")
