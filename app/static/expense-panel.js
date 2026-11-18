/* AETHER expense UI. Drafts/retry keys stay in page memory, never browser storage. */
(() => {
  "use strict";
  window.AetherExpensePanel = {create({api, credential, localDate, monthReport, amounts, onSaved}) {
    const $=id=>document.getElementById(id), form=$("expenseForm"), fields=form.elements;
    let editing=null,pending=null,busy=false,loadId=0,rows=[];
    const status=message=>$("expenseStatus").textContent=message;
    const summary=value=>value.currency+" "+value.amount+" · "+value.category+" · "+value.spent_on+(value.note?" · "+value.note:"");
    function controls(){
      for(const name of ["amount","currency","category","note","spent_on"])fields[name].disabled=busy;
      $("expenseSave").disabled=busy;$("expenseNew").disabled=busy;$("expenseReload").disabled=busy;
      $("expenseSave").textContent=busy?"Saving…":editing?"Review & save correction":pending?"Retry same expense":"Save expense";
      $("expenseFormTitle").textContent=editing?"Correct expense #"+editing.id:"Record expense";
      $("expenseNew").hidden=!editing&&!pending;
      for(const button of document.querySelectorAll("[data-exp-edit],[data-exp-del]"))button.disabled=busy||!!pending;
    }
    function fill(row){
      for(const name of ["amount","category","note","spent_on"])fields[name].value=row?.[name]??(name==="spent_on"?localDate():"");
      fields.currency.replaceChildren();const option=document.createElement("option");option.value=row?.currency||"INR";option.textContent=option.value;fields.currency.append(option);fields.currency.value=option.value;
    }
    function reset(){editing=null;pending=null;fill(null);controls();}
    $("expenseNew").onclick=()=>{
      if(busy)return;
      if(pending&&!window.confirm("The previous save may have reached the server. Check transactions before starting another expense, or you could create a duplicate. Discard this retry key and start a new record?"))return;
      reset();status("New INR expense draft. Nothing has been saved.");
    };
    function messageError(error){
      const detail=error?.message||"Request failed.";
      status(detail+(pending?" The outcome may be unknown. Keep these fields unchanged and retry with the same credential and key, or reload transactions to check. Reloading/closing this page loses the retry key.":" Refresh the transaction and review current values before retrying a conflicting correction."));
    }
    async function load(){
      const id=++loadId,actor=credential(),month=$("expenseMonth").value||localDate().slice(0,7);
      if(!actor){rows=[];$("expenseList").replaceChildren();status("Connect your device token to view expenses.");return;}
      const [data,report]=await Promise.all([api("/api/life/expenses?month="+encodeURIComponent(month)),monthReport(api,month)]);
      if(id!==loadId||actor!==credential())return;
      rows=data.items||[];$("expenseMonthTotal").textContent=amounts(report);
      $("expenseScope").textContent=[data.notice||"Local saved expenses only.",data.partial?"Transaction totals are partial.":"",data.items_truncated?"Only the first "+data.item_limit+" transactions are shown.":"",data.invalid_records_skipped?data.invalid_records_skipped+" invalid legacy rows skipped.":"",report.partial?"Monthly report totals are partial.":"",report.invalid_records_skipped?report.invalid_records_skipped+" invalid rows skipped by the monthly report.":""].filter(Boolean).join(" ");
      $("expenseCategories").replaceChildren();for(const value of report.by_category||[]){const line=document.createElement("div");line.className="item";line.textContent=value.category+" · "+value.currency+" "+value.amount;$("expenseCategories").append(line);}
      $("expenseList").replaceChildren();
      if(!rows.length){const empty=document.createElement("div");empty.className="empty";empty.textContent="No valid expenses recorded in this month.";$("expenseList").append(empty);}
      for(const row of rows){
        const line=document.createElement("div"),body=document.createElement("div"),title=document.createElement("div"),meta=document.createElement("div"),actions=document.createElement("div"),edit=document.createElement("button"),remove=document.createElement("button");
        line.className="item";body.className="item-main";title.className="item-title";meta.className="item-meta";actions.className="actions";
        title.textContent=row.category+" · "+row.currency+" "+Number(row.amount).toLocaleString("en-IN");meta.textContent=row.spent_on+" · "+row.note;body.append(title,meta);
        edit.type=remove.type="button";edit.textContent="Correct";edit.dataset.expEdit=String(row.id);edit.disabled=busy||!!pending||!row.revision;
        edit.onclick=()=>{if(busy||pending)return;editing={...row};fill(row);controls();status("Editing saved expense #"+row.id+". Review every field; no change is saved yet.");form.scrollIntoView({block:"nearest"});};
        remove.textContent="Delete";remove.className="danger";remove.dataset.expDel=String(row.id);remove.disabled=busy||!!pending;
        remove.onclick=async()=>{if(busy||pending||!window.confirm("Delete expense #"+row.id+"? "+summary(row)))return;busy=true;controls();try{await api("/api/life/expenses/"+row.id,{method:"DELETE"});status("Expense #"+row.id+" deleted locally.");if(editing?.id===row.id)reset();await onSaved();}catch(error){status((error?.message||"Delete failed.")+" Reload transactions to check the result before retrying.");}finally{busy=false;controls();}};
        actions.append(edit,remove);line.append(body,actions);$("expenseList").append(line);
      }
      controls();
    }
    form.onsubmit=async event=>{
      event.preventDefault();if(busy)return;
      const actor=credential();if(!actor){status("Connect your device token first.");return;}
      const value={amount:Number(fields.amount.value),currency:fields.currency.value,category:fields.category.value.trim(),note:fields.note.value,spent_on:fields.spent_on.value};
      if(!Number.isFinite(value.amount)||value.amount<0.01||!value.category||!/^\d{4}-\d{2}-\d{2}$/.test(value.spent_on)){status("Enter a positive amount, category and YYYY-MM-DD spending date.");return;}
      const serialized=JSON.stringify(value);
      if(pending&&(pending.credential!==actor||pending.payload!==serialized)){status("An earlier create has an uncertain outcome. Use the original credential and unchanged fields to retry, or check transactions and explicitly start a new record. Nothing sent.");return;}
      if(editing&&!window.confirm("Save this correction to expense #"+editing.id+"?\nBefore: "+summary(editing)+"\nAfter: "+summary(value)+"\nLocal record only. No payment or currency conversion."))return;
      if(!editing&&!pending){
        if(!window.crypto?.randomUUID){status("Secure retry-key generation is unavailable. Use a supported browser on HTTPS or localhost; nothing sent.");return;}
        pending={key:window.crypto.randomUUID(),payload:serialized,credential:actor};
      }
      busy=true;controls();status(editing?"Saving reviewed correction…":"Saving expense with a retry-safe request key…");
      const target=editing?.id;
      try{
        const saved=await api(target?"/api/life/expenses/"+target:"/api/life/expenses",{method:target?"PUT":"POST",headers:target?{}:{"Idempotency-Key":pending.key},body:target?JSON.stringify({...value,expected_revision:editing.revision}):pending.payload});
        reset();status("Expense #"+saved.id+(target?" corrected":" saved")+" locally. No payment was made.");
        try{await onSaved();}catch(error){status("Expense #"+saved.id+" was saved, but refresh failed. Reload transactions; do not submit it as a new expense.");}
      }catch(error){messageError(error);}finally{busy=false;controls();}
    };
    $("expenseReload").onclick=()=>load().catch(messageError);
    $("expenseMonth").value=localDate().slice(0,7);$("expenseMonth").onchange=()=>load().catch(messageError);
    $("disconnectBtn").addEventListener("click",()=>{++loadId;rows=[];$("expenseList").replaceChildren();$("expenseCategories").replaceChildren();$("expenseMonthTotal").textContent="—";$("expenseScope").textContent="";status(busy?"Disconnected while a save was in progress. It may still finish on the server; check transactions before creating another record.":pending?"Disconnected. An uncertain create retry key remains only in this page; reconnect the same credential to retry unchanged fields.":"Disconnected. No expense request will start without a token.");});
    fill(null);controls();return {load};
  }};
})();
