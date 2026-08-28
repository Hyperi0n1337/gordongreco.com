import {api, fmtBytes, idempotency} from './api.js';

const views = ['login-view','totp-view','enroll-view','recovery-codes-view','portal-view'];
const state = {me: null, requests: [], documents: []};
const show = (id) => views.forEach((item) => document.getElementById(item).classList.toggle('hidden', item !== id));
const $ = (id) => document.getElementById(id);

async function boot() {
  const params = new URL(location.href).searchParams;
  const invitation = params.get('invite');
  const token = params.get('token');
  if (invitation || token) {
    history.replaceState({}, '', location.pathname);
    const endpoint = invitation ? '/auth/invitation/consume' : '/auth/magic-link/consume';
    try { await api(endpoint, {method:'POST', body:{token: invitation || token}}); }
    catch (error) { showNotice('The secure link is invalid, expired, used, or revoked. Request a new link.'); }
  }
  try {
    state.me = await api('/me');
    $('logout').classList.remove('hidden');
    if (!state.me.user.totp_confirmed_at) return beginEnrollment();
    if (!state.me.step_up) return show('totp-view');
    await openPortal();
  } catch (error) {
    if (error.status === 401) show('login-view'); else showNotice(error.message);
  }
}

function showNotice(message) {
  show('login-view');
  const node = $('magic-status');
  node.textContent = message;
  node.classList.remove('hidden');
  node.focus();
}

$('magic-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  try {
    const result = await api('/auth/magic-link', {method:'POST', body:{email:$('email').value}});
    if (result.mode === 'fictional_loopback_demo' && result.delivery === 'sent') {
      showNotice('Email sent. Open the single-use Gordon Greco link in your inbox within 10 minutes.');
    } else if (result.mode === 'fictional_loopback_demo' && result.delivery === 'not_eligible') {
      showNotice('No test invitation is configured for that email address.');
    } else {
      showNotice('Check your email for a one-time secure link. The message may take a moment to arrive.');
    }
  } catch (_) {
    showNotice('The request was accepted. Check your email if the address has an active invitation.');
  } finally { button.disabled = false; }
});

$('totp-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await api('/auth/totp/step-up', {method:'POST', body:{code:$('totp-code').value}}); await openPortal(); }
  catch (error) { alert(error.message); }
});

$('recovery-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try { await api('/auth/recovery', {method:'POST', body:{recovery_code:$('recovery-code').value}}); await openPortal(); }
  catch (error) { alert(error.message); }
});

async function beginEnrollment() {
  show('enroll-view');
  const enrollment = await api('/auth/totp/enroll', {method:'POST'});
  $('totp-secret').textContent = enrollment.secret;
}

$('enroll-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const result = await api('/auth/totp/confirm', {method:'POST', body:{code:$('enroll-code').value}});
    $('recovery-codes').textContent = result.recovery_codes.join('\n');
    show('recovery-codes-view');
  } catch (error) { alert(error.message); }
});
$('codes-saved').addEventListener('click', openPortal);

async function openPortal() {
  state.me = await api('/me');
  if (['advisor','operations'].includes(state.me.role)) {
    location.replace('/portal/advisor.html');
    return;
  }
  show('portal-view');
  $('logout').classList.remove('hidden');
  $('welcome').textContent = `Welcome, ${state.me.user.display_name}`;
  await loadRequests();
}

async function loadRequests() {
  const result = await api('/document-requests');
  state.requests = result.requests;
  state.documents = result.documents;
  renderSummary();
  renderRequests();
}

function latestDocument(requestId) {
  return state.documents.find((document) => document.request_id === requestId);
}

function renderSummary() {
  const counts = {missing:0, inReview:0, complete:0, replace:0};
  state.requests.forEach((request) => {
    const doc = latestDocument(request.id);
    const value = doc?.state || request.status || 'missing';
    if (value === 'accepted') counts.complete += 1;
    else if (['quarantined','scanning','ready_for_review'].includes(value)) counts.inReview += 1;
    else if (['needs_replacement','rejected'].includes(value)) counts.replace += 1;
    else counts.missing += 1;
  });
  $('summary-grid').innerHTML = [
    ['Missing',counts.missing],['In review',counts.inReview],['Complete',counts.complete],['Replace',counts.replace]
  ].map(([label,count]) => `<div class="summary-card"><strong>${count}</strong><span>${label}</span></div>`).join('');
}

function renderRequests() {
  const list = $('request-list');
  list.replaceChildren();
  if (!state.requests.length) {
    list.innerHTML = '<div class="empty">No document requests are open.</div>';
    return;
  }
  state.requests.forEach((request) => {
    const fragment = $('request-template').content.cloneNode(true);
    const card = fragment.querySelector('.request-card');
    const doc = latestDocument(request.id);
    const currentState = doc?.state || request.status || 'missing';
    const pill = fragment.querySelector('.state-pill');
    pill.textContent = currentState.replaceAll('_',' ');
    pill.classList.add(currentState);
    fragment.querySelector('h3').textContent = request.title;
    fragment.querySelector('.description').textContent = request.description || 'No additional instructions.';
    fragment.querySelector('.due').textContent = request.due_at ? `Due ${new Date(request.due_at).toLocaleDateString()}` : 'No fixed due date';
    fragment.querySelector('.file-meta').textContent = doc ? `${doc.original_filename} · ${fmtBytes(doc.authoritative_size)}${doc.review_note ? ` · ${doc.review_note}` : ''}` : '';
    const zone = fragment.querySelector('.upload-zone');
    const input = fragment.querySelector('input[type=file]');
    const canUpload = ['missing','needs_replacement','rejected'].includes(currentState);
    zone.classList.toggle('hidden', !canUpload);
    const choose = () => input.click();
    zone.addEventListener('click', choose);
    zone.addEventListener('keydown', (event) => { if (['Enter',' '].includes(event.key)) {event.preventDefault(); choose();} });
    zone.addEventListener('dragover', (event) => {event.preventDefault(); zone.classList.add('dragover');});
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', (event) => {event.preventDefault(); zone.classList.remove('dragover'); if (event.dataTransfer.files[0]) uploadFile(request, event.dataTransfer.files[0], card);});
    input.addEventListener('change', () => {
      if (input.files[0]) uploadFile(request, input.files[0], card, card.dataset.resumeUploadId || null);
    });
    const resumeId = sessionStorage.getItem(`gg-upload:${request.id}`);
    if (resumeId && canUpload) {
      const button = document.createElement('button'); button.type='button'; button.textContent='Resume interrupted upload';
      button.addEventListener('click', () => resumeInterrupted(request, resumeId, card));
      fragment.querySelector('.request-actions').append(button);
    }
    list.append(fragment);
  });
}

const types = {pdf:'application/pdf',jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',txt:'text/plain',csv:'text/csv'};
async function uploadFile(request, file, card, resumeUploadId = null) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!types[ext] || file.size <= 0 || file.size > 25 * 1024 * 1024) {
    alert('Choose an allowed file no larger than 25 MB.'); return;
  }
  const progress = card.querySelector('.progress-wrap');
  const bar = progress.querySelector('progress');
  const label = progress.querySelector('.progress-label');
  progress.classList.remove('hidden');
  try {
    let uploadId;
    let remoteParts = new Map();
    if (resumeUploadId) {
      const status = await api(`/uploads/${resumeUploadId}`);
      if (status.state !== 'open' || Number(status.declared_size) !== file.size) {
        throw new Error('The selected file does not match the resumable upload or the upload expired.');
      }
      uploadId = resumeUploadId;
      remoteParts = new Map((status.remote_parts || []).map((part) => [Number(part.part_number), part]));
    } else {
      const start = await api('/uploads', {method:'POST', body:{
        request_id:request.id,
        filename:file.name,
        content_type:types[ext],
        size:file.size,
        idempotency_key:idempotency('upload')
      }});
      uploadId = start.upload_id;
    }
    sessionStorage.setItem(`gg-upload:${request.id}`, uploadId);
    card.dataset.resumeUploadId = uploadId;

    const partSize = 5 * 1024 * 1024;
    const parts = [];
    for (let offset=0, part=1; offset<file.size; offset+=partSize, part+=1) {
      const blob = file.slice(offset, Math.min(offset+partSize,file.size));
      const retained = remoteParts.get(part);
      if (retained && Number(retained.size) === blob.size && retained.etag) {
        parts.push({part_number:part,etag:retained.etag});
        label.textContent = `Retained verified part ${part}; continuing…`;
      } else {
        label.textContent = `Uploading part ${part}…`;
        const signed = await api(`/uploads/${uploadId}/parts/${part}/capability`, {method:'POST'});
        const result = await api(`/uploads/${uploadId}/parts/${part}`, {
          method:'PUT',
          headers:{'X-Upload-Capability':signed.capability,'Content-Type':'application/octet-stream'},
          body:blob
        });
        parts.push({part_number:part,etag:result.etag});
      }
      bar.value = Math.round((Math.min(offset+partSize,file.size)/file.size)*90);
    }
    label.textContent='Completing, hashing, and moving to quarantine…';
    await api(`/uploads/${uploadId}/complete`, {method:'POST',body:{parts}});
    bar.value=100; label.textContent='Uploaded. Security review is in progress.';
    sessionStorage.removeItem(`gg-upload:${request.id}`);
    delete card.dataset.resumeUploadId;
    setTimeout(loadRequests, 800);
  } catch (error) {
    label.textContent=`Upload paused: ${error.message}`;
  }
}

async function resumeInterrupted(request, uploadId, card) {
  try {
    const status = await api(`/uploads/${uploadId}`);
    if (status.state !== 'open') throw new Error('Upload is no longer open');
    card.dataset.resumeUploadId = uploadId;
    alert(`The server retained ${fmtBytes(status.uploaded_bytes)}. Choose the same file; matching remote parts will be reused and missing parts uploaded.`);
    card.querySelector('input[type=file]').click();
  } catch (_) {
    sessionStorage.removeItem(`gg-upload:${request.id}`);
    delete card.dataset.resumeUploadId;
    await loadRequests();
  }
}

$('refresh').addEventListener('click', loadRequests);
$('support-open').addEventListener('click', () => $('support-dialog').showModal());
$('support-cancel').addEventListener('click', () => $('support-dialog').close());
$('support-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {await api('/support',{method:'POST',body:{message:$('support-message').value}}); $('support-dialog').close(); $('support-message').value=''; alert('Your portal support request was sent.');}
  catch(error){alert(error.message);}
});
$('logout').addEventListener('click', async () => {try{await api('/auth/logout',{method:'POST'});}finally{location.replace('/portal/');}});

boot();
