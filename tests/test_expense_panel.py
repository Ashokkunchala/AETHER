"""Expense UI tests with synthetic responses, no browser account or real records."""
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'app/static/expense-panel.js'
PRELUDE = r"""
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element extends EventTarget{constructor(){super();this.value='';this.textContent='';this.disabled=false;this.hidden=false;this.children=[];this.dataset={};}append(...x){this.children.push(...x);}replaceChildren(...x){this.children=x;}scrollIntoView(){}click(){this.onclick?.();this.dispatchEvent(new Event('click'));}}
const e={};for(const id of ['expenseForm','expenseStatus','expenseSave','expenseNew','expenseReload','expenseFormTitle','expenseMonth','expenseList','expenseMonthTotal','expenseCategories','expenseScope','disconnectBtn'])e[id]=new Element();
e.expenseForm.elements={};for(const name of ['amount','currency','category','note','spent_on'])e.expenseForm.elements[name]=new Element();
const f=e.expenseForm.elements;global.document={getElementById:id=>e[id],createElement:()=>new Element(),querySelectorAll:()=>[]};
let actor='same-device',calls=[],confirmed=[],answer=true,after=0,afterFail=false,fail=false,hold=null,reply={id:1},payload={items:[],notice:'Separate currencies',partial:false},report={by_category:[]};
global.window={confirm:text=>{confirmed.push(text);return answer;},crypto:{randomUUID:()=> 'synthetic-retry-key'}};
const api=async(path,options={})=>{calls.push({path,...options});if(options.method){if(hold)await hold;if(fail)throw Error('Network outcome unknown');return reply;}return payload;};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const panel=window.AetherExpensePanel.create({api,credential:()=>actor,localDate:()=> '2026-11-16',monthReport:async()=>report,amounts:()=> 'INR 10.25',onSaved:async()=>{after++;if(afterFail)throw Error("refresh unavailable");}});
function draft(){f.amount.value='10.25';f.currency.value='INR';f.category.value='Food';f.note.value='Lunch';f.spent_on.value='2026-11-16';}
function submit(){return e.expenseForm.onsubmit({preventDefault(){}});}
function action(index=0,button=0){return e.expenseList.children[index].children[1].children[button];}
const row={id:1,amount:10.25,currency:'INR',category:'Food',note:'Lunch',spent_on:'2026-11-16',revision:'a'.repeat(64)};
(async()=>{
"""


def run(body):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for expense UI checks')
    source = PRELUDE + body + "\n})().catch(e=>{console.error(e);process.exitCode=1});"
    result = subprocess.run([node, '-e', source, str(SCRIPT)], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_create_has_retry_key_and_no_automatic_second_write():
    run("draft();await submit();assert.equal(calls.length,1);assert.equal(calls[0].method,'POST');assert.equal(calls[0].headers['Idempotency-Key'],'synthetic-retry-key');assert.equal(after,1);assert.equal(f.amount.value,'');assert(e.expenseStatus.textContent.includes('No payment'));")


def test_uncertain_create_retries_same_key_and_payload():
    run("draft();fail=true;await submit();assert(e.expenseStatus.textContent.includes('outcome may be unknown'));fail=false;await submit();assert.equal(calls.length,2);assert.equal(calls[0].body,calls[1].body);assert.deepEqual(calls[0].headers,calls[1].headers);")


def test_changed_payload_or_credential_never_reuses_key():
    run("draft();fail=true;await submit();f.amount.value='22';await submit();assert.equal(calls.length,1);f.amount.value='10.25';actor='different-device';await submit();assert.equal(calls.length,1);assert(e.expenseStatus.textContent.includes('Nothing sent'));")


def test_double_submit_is_blocked_and_controls_reenable():
    run("draft();let resolve;hold=new Promise(r=>resolve=r);const first=submit();assert(e.expenseSave.disabled);await submit();assert.equal(calls.length,1);resolve();await first;assert(!e.expenseSave.disabled);")


def test_new_record_after_uncertain_result_requires_explicit_discard():
    run("draft();fail=true;await submit();answer=false;e.expenseNew.click();assert.equal(f.amount.value,'10.25');answer=true;e.expenseNew.click();assert.equal(f.amount.value,'');assert(confirmed[0].includes('duplicate'));")


def test_correction_requires_exact_review_and_original_revision():
    run("payload.items=[row];await panel.load();action().click();f.amount.value='12.50';answer=false;await submit();assert.equal(calls.length,1);answer=true;await submit();assert.equal(calls[1].method,'PUT');assert.equal(calls[1].path,'/api/life/expenses/1');assert.equal(JSON.parse(calls[1].body).expected_revision,row.revision);assert.equal(calls[1].headers['Idempotency-Key'],undefined);assert(confirmed.at(-1).includes('Before: INR 10.25'));assert(confirmed.at(-1).includes('After: INR 12.5'));")


def test_foreign_legacy_correction_preserves_currency_and_cancel_resets_inr():
    run("payload.items=[{...row,currency:'USD'}];await panel.load();action().click();assert.equal(f.currency.value,'USD');e.expenseNew.click();assert.equal(f.currency.value,'INR');assert.equal(f.amount.value,'');")


def test_stale_correction_error_keeps_draft_and_does_not_automatically_retry():
    run("payload.items=[row];await panel.load();action().click();f.amount.value='15';fail=true;await submit();assert.equal(f.amount.value,'15');assert(e.expenseStatus.textContent.includes('review current values'));assert.equal(calls.filter(x=>x.method).length,1);")


def test_refresh_failure_after_success_never_leaves_a_retryable_new_expense():
    run("draft();afterFail=true;await submit();assert.equal(after,1);assert(e.expenseStatus.textContent.includes('was saved, but refresh failed'));e.expenseNew.click();assert.equal(confirmed.length,0);")


def test_no_token_no_secure_key_or_invalid_fields_never_write():
    run("draft();actor='';await submit();assert.equal(calls.length,0);actor='same-device';window.crypto={};await submit();assert.equal(calls.length,0);f.amount.value='-1';await submit();assert.equal(calls.length,0);")


def test_partial_scope_invalid_rows_and_untrusted_text_are_visible_as_text():
    run("payload={items:[{...row,category:'<script>literal</script>'}],notice:'Bounded local records',partial:true,items_truncated:true,item_limit:1000,invalid_records_skipped:2};report={by_category:[{category:'<img>',currency:'INR',amount:'10.25'}],partial:true,invalid_records_skipped:1};await panel.load();assert(e.expenseScope.textContent.includes('partial'));assert(e.expenseScope.textContent.includes('2 invalid'));assert(e.expenseCategories.children[0].textContent.includes('<img>'));assert(e.expenseList.children[0].children[0].children[0].textContent.includes('<script>'));assert.equal(e.expenseList.children[0].innerHTML,undefined);")


def test_disconnect_discards_stale_read_and_keeps_unknown_create_state():
    run("draft();fail=true;await submit();actor='';e.disconnectBtn.click();assert(e.expenseStatus.textContent.includes('uncertain'));assert.equal(e.expenseList.children.length,0);actor='same-device';fail=false;await submit();assert.equal(calls[1].headers['Idempotency-Key'],'synthetic-retry-key');")


def test_ui_never_persists_expense_drafts_keys_or_token():
    source = SCRIPT.read_text()
    assert 'localStorage' not in source and 'sessionStorage' not in source
    assert 'innerHTML' not in source and 'insertAdjacentHTML' not in source
    assert 'fetch(' not in source  # Uses existing authenticated api helper only.
