import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
const source=fs.readFileSync(new URL('../src/worker.mjs',import.meta.url),'utf8');
test('portal is fail closed and scope derived',()=>{for(const text of ['admin_required','session_required','origin_rejected','csrf_or_session_failed','household_id=?','content_type_rejected','file_size_rejected','quarantined','stale_revision'])assert.ok(source.includes(text),text)});
test('secrets and private identifiers are not logged',()=>{assert.ok(!/console\.log/.test(source));assert.ok(!/password|\bssn\b|\bein\b|security answer/i.test(source));assert.ok(source.includes("console.error('request_failed'"))});
test('portal never exposes inline active content',()=>{assert.ok(source.includes("content-disposition':`attachment"));assert.ok(source.includes("content-security-policy':\"default-src 'none'; sandbox\""));assert.ok(source.includes("x-content-type-options':'nosniff'"))});
