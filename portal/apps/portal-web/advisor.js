import {api, fmtBytes, idempotency} from './api.js';
const $ = (id) => document.getElementById(id);
let me;
function toast(message){const node=$('toast');node.textContent=message;node.classList.remove('hidden');setTimeout(()=>node.classList.add('hidden'),4000)}
function formObject(form){return Object.fromEntries(new FormData(form).entries())}

async function boot(){
  try{me=await api('/me');if(!['advisor','operations'].includes(me.role)){location.replace('/portal/');return;}await Promise.all([loadDocuments(),loadTreasury()]);}
  catch(error){if(error.status===401)location.replace('/portal/');else toast(error.message)}
}

document.querySelectorAll('.tabs button').forEach((button)=>button.addEventListener('click',()=>{
  document.querySelectorAll('.tabs button').forEach((item)=>item.classList.toggle('active',item===button));
  document.querySelectorAll('.tab-panel').forEach((panel)=>panel.classList.toggle('hidden',panel.id!==button.dataset.tab));
}));

$('step-up').addEventListener('click',async()=>{const code=prompt('Enter the 6-digit authenticator code.');if(!code)return;try{await api('/auth/totp/step-up',{method:'POST',body:{code}});me=await api('/me');toast('Security check complete for 15 minutes.')}catch(error){toast(error.message)}});

$('request-form').addEventListener('submit',async(event)=>{event.preventDefault();const value=formObject(event.currentTarget);value.entity_id=value.entity_id||null;value.due_at=value.due_at?new Date(value.due_at).toISOString():null;try{await api('/advisor/document-requests',{method:'POST',body:value});event.currentTarget.reset();toast('Document request created.');await loadDocuments()}catch(error){toast(error.message)}});

async function loadDocuments(){
  const data=await api('/document-requests');const list=$('advisor-documents');list.replaceChildren();
  const requestById=Object.fromEntries(data.requests.map((item)=>[item.id,item]));
  if(!data.documents.length){list.innerHTML='<div class="empty">No uploaded documents are in scope.</div>';return;}
  data.documents.forEach((doc)=>{const request=requestById[doc.request_id]||{};const card=document.createElement('article');card.className='request-card';card.innerHTML=`<div class="request-copy"><div class="request-topline"><span class="state-pill ${doc.state}">${doc.state.replaceAll('_',' ')}</span></div><h3>${escapeHtml(request.title||'Document')}</h3><p class="file-meta">${escapeHtml(doc.original_filename)} · ${fmtBytes(doc.authoritative_size)}</p><p class="description">${escapeHtml(doc.review_note||'')}</p></div><div class="request-actions"></div>`;
    const actions=card.querySelector('.request-actions');
    if(['ready_for_review','needs_replacement'].includes(doc.state)){['accept','replace','reject'].forEach((decision)=>{const b=document.createElement('button');b.textContent=decision[0].toUpperCase()+decision.slice(1);b.addEventListener('click',()=>review(doc,decision));actions.append(b)})}
    if(['ready_for_review','accepted'].includes(doc.state)){const b=document.createElement('button');b.textContent='Secure download';b.addEventListener('click',()=>download(doc));actions.append(b)}
    if(doc.state!=='deleted'&&me.role==='advisor'){const b=document.createElement('button');b.className='danger';b.textContent='Delete';b.addEventListener('click',()=>remove(doc));actions.append(b)}
    list.append(card);
  });
}
function escapeHtml(value){const span=document.createElement('span');span.textContent=value||'';return span.innerHTML}
async function review(doc,decision){const note=prompt(`Optional note for ${decision}:`)||'';try{await api(`/advisor/documents/${doc.id}/review`,{method:'POST',body:{decision,note,expected_revision:doc.revision||1}});toast(`Document marked ${decision}.`);await loadDocuments()}catch(error){toast(error.message)}}
async function download(doc){try{const result=await api(`/advisor/documents/${doc.id}/download`);location.assign(result.url)}catch(error){if(error.code==='totp_step_up_required')toast('Complete the security check first.');else toast(error.message)}}
async function remove(doc){const reason=prompt('Deletion reason (recorded permanently):');if(!reason)return;try{await api(`/advisor/documents/${doc.id}/delete`,{method:'POST',body:{reason,expected_revision:doc.revision||1}});toast('Deletion queued and receipt recorded.');await loadDocuments()}catch(error){toast(error.message)}}
$('documents-refresh').addEventListener('click',loadDocuments);

$('invite-form').addEventListener('submit',async(event)=>{event.preventDefault();const v=formObject(event.currentTarget);const body={...v,entity_ids:v.entity_ids?v.entity_ids.split(',').map(x=>x.trim()).filter(Boolean):[],expires_in_days:7};try{await api('/advisor/invitations',{method:'POST',body});event.currentTarget.reset();toast('Invitation queued for outbound delivery.')}catch(error){toast(error.message)}});
$('revoke-form').addEventListener('submit',async(event)=>{event.preventDefault();const v=formObject(event.currentTarget);if(!confirm('Revoke this membership and every current session?'))return;try{await api('/advisor/revocations',{method:'POST',body:v});event.currentTarget.reset();toast('Access revoked immediately.')}catch(error){toast(error.message)}});

$('policy-form').addEventListener('submit',async(event)=>{event.preventDefault();const v=formObject(event.currentTarget);const body={household_id:v.household_id,base_version_id:v.base_version_id||null,effective_at:new Date(v.effective_at).toISOString(),terms:{currency:v.currency.toUpperCase(),minimum_operating_reserve_minor:Number(v.reserve),cash_operation_limit_minor:Number(v.limit),permitted_operation_types:['operating_reserve_adjustment','planned_tax_payment_reserve','same_entity_liquidity_allocation','external_cash_need_notice']},signer_user_ids:v.signers.split(',').map(x=>x.trim()).filter(Boolean),approval_threshold:Number(v.threshold),idempotency_key:idempotency('policy')};try{await api('/treasury/policies',{method:'POST',body});toast('Future-effective policy version proposed.');await loadTreasury()}catch(error){toast(error.message)}});
$('cash-form').addEventListener('submit',async(event)=>{event.preventDefault();const v=formObject(event.currentTarget);const body={household_id:v.household_id,entity_id:v.entity_id||null,policy_version_id:v.policy_version_id,operation_type:v.operation_type,amount_minor:Number(v.amount_minor),currency:v.currency.toUpperCase(),requested_effective_at:new Date(v.requested_effective_at).toISOString(),rationale:v.rationale,conflict_key:v.conflict_key,idempotency_key:idempotency('cash')};try{await api('/treasury/cash-operations',{method:'POST',body});toast('Cash operation entered approval workflow; no execution occurred.');await loadTreasury()}catch(error){toast(error.message)}});
async function loadTreasury(){try{const data=await api('/treasury');const list=$('treasury-state');list.replaceChildren();const rows=[...data.policies.map(x=>({...x,kind:'Policy'})),...data.cash_operations.map(x=>({...x,kind:'Cash operation'}))];if(!rows.length){list.innerHTML='<div class="empty">No treasury workflows are in scope.</div>';return;}rows.forEach((row)=>{const card=document.createElement('article');card.className='request-card';const state=row.state||'unknown';card.innerHTML=`<div><div class="request-topline"><span class="state-pill ${state}">${escapeHtml(state.replaceAll('_',' '))}</span></div><h3>${row.kind} ${escapeHtml(row.id)}</h3><p class="description">Household ${escapeHtml(row.household_id)} · revision ${row.revision||1} · execution: ${escapeHtml(row.execution_state||'none')}</p></div><div class="request-actions"></div>`;if(state==='pending_approval'){const b=document.createElement('button');b.textContent='Approve with step-up';b.addEventListener('click',async()=>{try{const path=row.kind==='Policy'?`/treasury/policies/${row.id}/approve`:`/treasury/cash-operations/${row.id}/approve`;await api(path,{method:'POST',body:{expected_revision:row.revision||1}});toast('Approval recorded.');await loadTreasury()}catch(error){toast(error.message)}});card.querySelector('.request-actions').append(b)}list.append(card)})}catch(error){toast(error.message)}}
$('treasury-refresh').addEventListener('click',loadTreasury);
$('logout').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'})}finally{location.replace('/portal/')}});
boot();
