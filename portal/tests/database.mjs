// Actual PostgreSQL SQL/PLpgSQL in memory. No RDS connection or persistent service.
// PGlite has one connection; it cannot prove multi-connection race behavior.
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const db = new PGlite();
const read = name => readFile(new URL(`../../migrations/sql/${name}`,import.meta.url),'utf8');
let checks=0;
const employee='10000000-0000-4000-8000-000000000001';
const engineer='10000000-0000-4000-8000-000000000002';
const other='10000000-0000-4000-8000-000000000003';
async function deny(statement, params=[], code='P0001') {
  await db.exec('SAVEPOINT denied');
  try { await db.query(statement,params); assert.fail('Statement unexpectedly succeeded'); }
  catch(e) { assert.equal(e.code,code,e.message); checks++; }
  finally { await db.exec('ROLLBACK TO SAVEPOINT denied; RELEASE SAVEPOINT denied'); }
}
async function actor(id, kind) {
  await db.query("SELECT set_config('sahayak.actor_id',$1,true),set_config('sahayak.actor_kind',$2,true),set_config('sahayak.reason','Integration test',true)",[id,kind]);
}
async function count(table) { return Number((await db.query(`SELECT count(*) AS n FROM sahayak.${table}`)).rows[0].n); }
const insert="INSERT INTO sahayak.tickets(employee_id,request_key,category,description,priority,callback_at) VALUES ($1,$2,'account_access','Locked out and cannot work','low',now()+interval '1 day') RETURNING *";
try {
  await db.exec(await read('0001_baseline.sql'));
  await db.exec("CREATE TABLE public.alembic_version(version_num varchar(32) PRIMARY KEY); INSERT INTO public.alembic_version VALUES ('0002_portal')");
  await db.exec(await read('0002_portal.sql'));
  const current=(await db.query('SELECT current_database() AS name')).rows[0].name;
  await db.exec((await read('runtime_grants.sql')).replace('CONNECT ON DATABASE sahayak','CONNECT ON DATABASE '+current));
  checks++;
  await db.exec('BEGIN');
  for (const [id,role] of [[employee,'employee'],[engineer,'engineer'],[other,'engineer']]) {
    await db.query("INSERT INTO sahayak.profiles(id,identity_issuer,identity_subject,employee_code,display_name,email,phone_e164,phone_trusted_at,phone_trusted_by,phone_trust_method) VALUES($1::uuid,'urn:test',$1::text,$1::text,'Test','test@example.invalid','+919999999999',now(),'test','rollback fixture')",[id]);
    await db.query('INSERT INTO sahayak.profile_roles VALUES ($1,$2)',[id,role]);
  }
  await db.exec('SET LOCAL ROLE sahayak_portal');
  const key='20000000-0000-4000-8000-000000000001';
  await deny(insert,[employee,key]);
  await actor(employee,'employee');
  await deny(insert,[engineer,key]);
  const t=(await db.query(insert,[employee,key])).rows[0];
  assert.equal(t.priority,'critical'); assert.equal(t.status,'new'); checks++;
  await db.query(insert.replace(' RETURNING *',' ON CONFLICT (employee_id,request_key) DO NOTHING'),[employee,key]);
  await deny('UPDATE sahayak.profiles SET active=false WHERE id=$1',[employee],'42501');
  await deny('DELETE FROM sahayak.tickets WHERE id=$1',[t.id],'42501');
  await deny('UPDATE sahayak.outbox_events SET published_at=now() WHERE ticket_id=$1',[t.id],'42501');
  await deny('UPDATE sahayak.tickets SET assigned_engineer_id=$1 WHERE id=$2',[employee,t.id]);
  await actor(engineer,'engineer');
  await deny('UPDATE sahayak.tickets SET assigned_engineer_id=$1 WHERE id=$2',[engineer,t.id]);
  await db.exec('RESET ROLE');
  assert.equal(await count('tickets'),1); assert.equal(await count('ticket_events'),1); assert.equal(await count('outbox_events'),1); checks++;
  const times=(await db.query('SELECT o.available_at=t.callback_at AND c.due_at=t.callback_at AS correct FROM sahayak.tickets t JOIN sahayak.outbox_events o ON o.ticket_id=t.id JOIN sahayak.callback_requests c ON c.ticket_id=t.id')).rows[0];
  assert.equal(times.correct,true); checks++;
  // A failure in the final outbox insert must roll back ticket AND audit inserts.
  await db.exec("ALTER TABLE sahayak.outbox_events ADD CONSTRAINT test_failure CHECK(event_type <> 'ai.call.requested') NOT VALID; SET LOCAL ROLE sahayak_portal");
  await actor(employee,'employee');
  await deny(insert,[employee,'20000000-0000-4000-8000-000000000002'],'23514');
  await db.exec('RESET ROLE; ALTER TABLE sahayak.outbox_events DROP CONSTRAINT test_failure');
  assert.equal(await count('tickets'),1); assert.equal(await count('ticket_events'),1); checks++;
  // Simulate an agent-escalated fixture, then immediately re-enable the guard.
  await db.exec('ALTER TABLE sahayak.tickets DISABLE TRIGGER tickets_portal_guard');
  await db.query("UPDATE sahayak.tickets SET status='transferred_to_human' WHERE id=$1",[t.id]);
  await db.exec('ALTER TABLE sahayak.tickets ENABLE TRIGGER tickets_portal_guard; SET LOCAL ROLE sahayak_portal');
  await actor(engineer,'engineer');
  const claimed=(await db.query('UPDATE sahayak.tickets SET assigned_engineer_id=$1 WHERE id=$2 RETURNING *',[engineer,t.id])).rows[0];
  assert.equal(claimed.version,2); assert.equal(claimed.assigned_engineer_id,engineer); checks++;
  await actor(other,'engineer');
  await deny('UPDATE sahayak.tickets SET assigned_engineer_id=$1 WHERE id=$2',[other,t.id]);
  await deny("UPDATE sahayak.tickets SET status='completed',resolved_by_kind='engineer',resolved_by_profile_id=$1,resolution_summary='Fixed' WHERE id=$2",[other,t.id]);
  await actor(engineer,'engineer');
  await deny("UPDATE sahayak.tickets SET status='completed',resolved_by_kind='engineer',resolved_by_profile_id=$1,resolution_summary=' ' WHERE id=$2",[engineer,t.id]);
  const done=(await db.query("UPDATE sahayak.tickets SET status='completed',resolved_by_kind='engineer',resolved_by_profile_id=$1,resolution_summary='Fixed and confirmed' WHERE id=$2 RETURNING *",[engineer,t.id])).rows[0];
  assert.equal(done.version,3); assert.equal(done.status,'completed'); checks++;
  await deny("UPDATE sahayak.tickets SET status='new' WHERE id=$1",[t.id]);
  await db.exec('RESET ROLE');
  const events=(await db.query('SELECT event_type FROM sahayak.ticket_events ORDER BY id')).rows.map(r=>r.event_type);
  assert.deepEqual(events,['ticket.created','ticket.assigned','ticket.completed']);
  assert.equal(await count('outbox_events'),1); checks++;
  await deny("UPDATE sahayak.ticket_events SET note='rewrite' WHERE ticket_id=$1",[t.id]);
  await db.exec('ROLLBACK');
  assert.equal(await count('profiles'),0); assert.equal(await count('tickets'),0); checks++;
  console.log(`PASS: ${checks} PostgreSQL migration, audit, rollback and privilege checks. No RDS access.`);
} catch (error) { console.error('Database check failed:', error.message, error.code ?? ''); process.exitCode=1; } finally { await db.close(); }
