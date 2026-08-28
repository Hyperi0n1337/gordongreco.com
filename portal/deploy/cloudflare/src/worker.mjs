const JSON_HEADERS = {'content-type':'application/json; charset=utf-8','cache-control':'no-store'};
const ALLOWED_TYPES = new Set(['application/pdf','image/jpeg','image/png','text/plain','text/csv','application/csv']);

function json(body, status=200, headers={}) { return new Response(JSON.stringify(body), {status, headers:{...JSON_HEADERS,...headers}}); }
function fail(status, code) { return json({error:{code}}, status); }
function randomToken(bytes=32) { const data=new Uint8Array(bytes); crypto.getRandomValues(data); return btoa(String.fromCharCode(...data)).replaceAll('+','-').replaceAll('/','_').replaceAll('=',''); }
async function sha256(value) { const data=typeof value==='string'?new TextEncoder().encode(value):value; return [...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(x=>x.toString(16).padStart(2,'0')).join(''); }
async function secureEqual(a,b) { if(!a||!b)return false; const [x,y]=await Promise.all([sha256(a),sha256(b)]); return x===y; }
function cookies(request) { return Object.fromEntries((request.headers.get('cookie')||'').split(';').map(x=>x.trim()).filter(Boolean).map(x=>{const i=x.indexOf('=');return [x.slice(0,i),decodeURIComponent(x.slice(i+1))]})); }
function cookie(name,value,maxAge,{httpOnly=true}={}) { return `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; Secure; SameSite=Strict${httpOnly?'; HttpOnly':''}`; }
function nowIso() { return new Date().toISOString(); }
function futureIso(seconds) { return new Date(Date.now()+seconds*1000).toISOString(); }

async function bodyJson(request) { try { return await request.json(); } catch { throw new Response(null,{status:400}); } }
async function audit(env, actor, household, action, type, id, detail={}) { await env.DB.prepare('INSERT INTO audit_events(id,actor_id,household_id,action,object_type,object_id,detail_json) VALUES(?,?,?,?,?,?,?)').bind(crypto.randomUUID(),actor,household||null,action,type,id,JSON.stringify(detail)).run(); }

async function admin(request, env) { const value=(request.headers.get('authorization')||'').replace(/^Bearer\s+/i,''); return secureEqual(value,env.ADMIN_API_KEY); }

async function session(request, env) {
  const raw=cookies(request).gg_session;
  if(!raw)return null;
  const hash=await sha256(`${env.SESSION_PEPPER}:${raw}`);
  return env.DB.prepare(`SELECT s.id session_id,s.csrf,s.expires_at,u.id user_id,u.email,u.display_name,u.household_id,h.name household_name
    FROM sessions s JOIN users u ON u.id=s.user_id JOIN households h ON h.id=u.household_id
    WHERE s.token_hash=? AND s.expires_at>CURRENT_TIMESTAMP AND u.active=1`).bind(hash).first();
}

async function csrf(request, env) {
  const row=await session(request,env); if(!row)return null;
  const token=request.headers.get('x-csrf-token')||'';
  return await secureEqual(token,row.csrf)?row:null;
}

async function createInvitation(request, env, url) {
  if(!await admin(request,env))return fail(401,'admin_required');
  const b=await bodyJson(request);
  if(!b.email||!b.display_name||!b.household_id||!b.household_name)return fail(422,'missing_required_field');
  const token=randomToken(), tokenHash=await sha256(`${env.SESSION_PEPPER}:${token}`);
  const userId=b.user_id||crypto.randomUUID(), inviteId=crypto.randomUUID();
  const expiry=futureIso(Math.min(Number(b.expires_in_seconds)||604800,604800));
  const statements=[
    env.DB.prepare('INSERT OR IGNORE INTO households(id,name) VALUES(?,?)').bind(b.household_id,b.household_name),
    env.DB.prepare(`INSERT INTO users(id,email,display_name,household_id) VALUES(?,?,?,?) ON CONFLICT(email) DO UPDATE SET display_name=excluded.display_name,household_id=excluded.household_id,active=1`).bind(userId,String(b.email).toLowerCase(),b.display_name,b.household_id),
    env.DB.prepare('INSERT INTO invitations(id,user_id,token_hash,expires_at) VALUES(?,?,?,?)').bind(inviteId,userId,tokenHash,expiry),
  ];
  for(const item of b.document_requests||[]) statements.push(env.DB.prepare('INSERT OR IGNORE INTO document_requests(id,household_id,title,description,due_at) VALUES(?,?,?,?,?)').bind(item.id||crypto.randomUUID(),b.household_id,item.title,String(item.description||''),item.due_at||null));
  await env.DB.batch(statements);
  await audit(env,'admin',b.household_id,'invitation.created','invitation',inviteId,{email:String(b.email).toLowerCase()});
  return json({invitation_id:inviteId,expires_at:expiry,invitation_url:`${url.origin}/portal/?token=${token}`},201);
}

async function consumeInvitation(request, env) {
  const b=await bodyJson(request), token=String(b.token||''); if(!token)return fail(422,'token_required');
  const hash=await sha256(`${env.SESSION_PEPPER}:${token}`);
  const invite=await env.DB.prepare(`SELECT i.id,i.user_id,u.household_id FROM invitations i JOIN users u ON u.id=i.user_id WHERE i.token_hash=? AND i.consumed_at IS NULL AND i.revoked_at IS NULL AND i.expires_at>CURRENT_TIMESTAMP`).bind(hash).first();
  if(!invite)return fail(401,'invalid_or_expired_invitation');
  const raw=randomToken(), sessionHash=await sha256(`${env.SESSION_PEPPER}:${raw}`), csrfToken=randomToken(24), seconds=Math.min(Number(env.SESSION_SECONDS)||3600,43200), sessionId=crypto.randomUUID();
  await env.DB.batch([
    env.DB.prepare('UPDATE invitations SET consumed_at=CURRENT_TIMESTAMP WHERE id=? AND consumed_at IS NULL').bind(invite.id),
    env.DB.prepare('INSERT INTO sessions(id,user_id,token_hash,csrf,expires_at) VALUES(?,?,?,?,?)').bind(sessionId,invite.user_id,sessionHash,csrfToken,futureIso(seconds)),
  ]);
  await audit(env,invite.user_id,invite.household_id,'invitation.consumed','invitation',invite.id);
  const headers=new Headers(JSON_HEADERS); headers.append('set-cookie',cookie('gg_session',raw,seconds)); headers.append('set-cookie',cookie('gg_csrf',csrfToken,seconds,{httpOnly:false}));
  return new Response(JSON.stringify({ok:true}),{status:200,headers});
}

async function me(request,env) { const s=await session(request,env); return s?json({id:s.user_id,email:s.email,display_name:s.display_name,household_id:s.household_id,household_name:s.household_name,role:'client'}):fail(401,'session_required'); }
async function checklist(request,env) { const s=await session(request,env); if(!s)return fail(401,'session_required'); const rows=await env.DB.prepare('SELECT id,title,description,status,due_at,updated_at FROM document_requests WHERE household_id=? ORDER BY created_at').bind(s.household_id).all(); return json({items:rows.results||[]}); }

async function upload(request,env) {
  const s=await csrf(request,env); if(!s)return fail(403,'csrf_or_session_failed');
  const form=await request.formData(), requestId=String(form.get('request_id')||''), file=form.get('file');
  if(!(file instanceof File)||!requestId)return fail(422,'request_and_file_required');
  const max=Math.min(Number(env.MAX_UPLOAD_BYTES)||20971520,20971520);
  if(file.size<1||file.size>max)return fail(413,'file_size_rejected');
  if(!ALLOWED_TYPES.has(file.type))return fail(415,'content_type_rejected');
  const target=await env.DB.prepare('SELECT id FROM document_requests WHERE id=? AND household_id=?').bind(requestId,s.household_id).first(); if(!target)return fail(404,'document_request_not_found');
  const bytes=await file.arrayBuffer(), digest=await sha256(bytes), id=crypto.randomUUID(), key=`quarantine/${s.household_id}/${id}`;
  await env.DOCUMENTS.put(key,bytes,{metadata:{contentType:file.type,sha256:digest,bytes:String(file.size)}});
  try {
    await env.DB.batch([
      env.DB.prepare('INSERT INTO documents(id,request_id,household_id,kv_key,display_name,content_type,bytes,sha256) VALUES(?,?,?,?,?,?,?,?)').bind(id,requestId,s.household_id,key,String(file.name).slice(0,240),file.type,file.size,digest),
      env.DB.prepare("UPDATE document_requests SET status='quarantined',updated_at=CURRENT_TIMESTAMP WHERE id=? AND household_id=?").bind(requestId,s.household_id),
    ]);
  } catch(error) { await env.DOCUMENTS.delete(key); throw error; }
  await audit(env,s.user_id,s.household_id,'document.uploaded','document',id,{request_id:requestId,bytes:file.size,sha256:digest});
  return json({document_id:id,status:'quarantined',bytes:file.size,sha256:digest},201);
}

async function support(request,env) { const s=await csrf(request,env); if(!s)return fail(403,'csrf_or_session_failed'); const b=await bodyJson(request), message=String(b.message||'').trim(); if(!message||message.length>2000)return fail(422,'invalid_message'); const id=crypto.randomUUID(); await env.DB.prepare('INSERT INTO support_requests(id,user_id,household_id,message) VALUES(?,?,?,?)').bind(id,s.user_id,s.household_id,message).run(); await audit(env,s.user_id,s.household_id,'support.requested','support_request',id); return json({id,status:'received'},201); }

async function logout(request,env) { const s=await csrf(request,env); if(s)await env.DB.prepare('DELETE FROM sessions WHERE id=?').bind(s.session_id).run(); const headers=new Headers(); headers.append('set-cookie',cookie('gg_session','',0)); headers.append('set-cookie',cookie('gg_csrf','',0,{httpOnly:false})); return new Response(null,{status:204,headers}); }

async function adminDocuments(request,env,url) { if(!await admin(request,env))return fail(401,'admin_required'); const rows=await env.DB.prepare(`SELECT d.id,d.household_id,d.display_name,d.content_type,d.bytes,d.sha256,d.status,d.revision,d.created_at,r.title request_title FROM documents d JOIN document_requests r ON r.id=d.request_id ORDER BY d.created_at DESC`).all(); return json({documents:rows.results||[]}); }
async function adminDownload(request,env,id) { if(!await admin(request,env))return fail(401,'admin_required'); const row=await env.DB.prepare('SELECT * FROM documents WHERE id=? AND status<>\'deleted\'').bind(id).first(); if(!row)return fail(404,'document_not_found'); const value=await env.DOCUMENTS.get(row.kv_key,'arrayBuffer'); if(!value)return fail(404,'object_not_found'); await audit(env,'admin',row.household_id,'document.downloaded','document',id); return new Response(value,{headers:{'content-type':'application/octet-stream','content-disposition':`attachment; filename="document-${id}"`,'x-content-type-options':'nosniff','cache-control':'no-store','content-security-policy':"default-src 'none'; sandbox"}}); }
async function adminReview(request,env,id) { if(!await admin(request,env))return fail(401,'admin_required'); const b=await bodyJson(request), decision=String(b.decision||''); if(!['accepted','replace'].includes(decision))return fail(422,'invalid_decision'); const row=await env.DB.prepare('SELECT household_id,request_id,revision FROM documents WHERE id=?').bind(id).first(); if(!row)return fail(404,'document_not_found'); if(Number(b.expected_revision)!==Number(row.revision))return fail(409,'stale_revision'); await env.DB.batch([env.DB.prepare('UPDATE documents SET status=?,revision=revision+1,reviewed_at=CURRENT_TIMESTAMP WHERE id=? AND revision=?').bind(decision,id,row.revision),env.DB.prepare('UPDATE document_requests SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?').bind(decision==='accepted'?'complete':'replace',row.request_id)]); await audit(env,'admin',row.household_id,'document.reviewed','document',id,{decision}); return json({id,status:decision,revision:Number(row.revision)+1}); }

async function route(request,env) {
  const url=new URL(request.url), path=url.pathname;
  if(request.method!=='GET'&&request.method!=='HEAD') { const origin=request.headers.get('origin'); if(origin&&origin!==url.origin)return fail(403,'origin_rejected'); }
  if(path==='/api/v1/admin/invitations'&&request.method==='POST')return createInvitation(request,env,url);
  if(path==='/api/v1/auth/invitation/consume'&&request.method==='POST')return consumeInvitation(request,env);
  if(path==='/api/v1/me'&&request.method==='GET')return me(request,env);
  if(path==='/api/v1/document-requests'&&request.method==='GET')return checklist(request,env);
  if(path==='/api/v1/uploads'&&request.method==='POST')return upload(request,env);
  if(path==='/api/v1/support'&&request.method==='POST')return support(request,env);
  if(path==='/api/v1/auth/logout'&&request.method==='POST')return logout(request,env);
  if(path==='/api/v1/admin/documents'&&request.method==='GET')return adminDocuments(request,env,url);
  const download=path.match(/^\/api\/v1\/admin\/documents\/([^/]+)\/download$/); if(download&&request.method==='GET')return adminDownload(request,env,download[1]);
  const review=path.match(/^\/api\/v1\/admin\/documents\/([^/]+)\/review$/); if(review&&request.method==='POST')return adminReview(request,env,review[1]);
  if(path.startsWith('/api/'))return fail(404,'route_not_found');
  if(path==='/'||path==='/portal')return Response.redirect(`${url.origin}/portal/`,302);
  return env.ASSETS.fetch(request);
}

export default { async fetch(request,env) { try { const response=await route(request,env); const headers=new Headers(response.headers); headers.set('x-content-type-options','nosniff'); headers.set('referrer-policy','no-referrer'); headers.set('permissions-policy','camera=(), microphone=(), geolocation=()'); headers.set('x-frame-options','DENY'); if((new URL(request.url)).pathname.startsWith('/portal'))headers.set('content-security-policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"); return new Response(response.body,{status:response.status,statusText:response.statusText,headers}); } catch(error) { console.error('request_failed',error?.name||'Error'); return fail(500,'internal_error'); } } };
