// Real PostgreSQL SQL in memory; no RDS/AWS. Single connection, not a race test.
import {PGlite} from '@electric-sql/pglite';
import {readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=new URL('../../',import.meta.url);
const sql=JSON.parse(execFileSync(fileURLToPath(new URL('.venv/bin/python',root)),[fileURLToPath(new URL('tests/export_dispatch_sql.py',root))],{encoding:'utf8'}));
const db=new PGlite(); let checks=0;
const read=n=>readFile(new URL('migrations/sql/'+n,root),'utf8');
async function run(query,params={}) {
 const values=[]; const bound=query.replace(/(?<!:):([a-z_]+)/g,(_,name)=>{assert.ok(name in params,name);values.push(params[name]);return '$'+values.length;});
 return db.query(bound,values);
}
async function deny(query,code='42501') {
 await db.exec('SAVEPOINT denied');
 try { await db.exec(query); assert.fail('Unexpectedly permitted'); }
 catch(e){assert.equal(e.code,code);checks++;}
 finally{await db.exec('ROLLBACK TO SAVEPOINT denied; RELEASE SAVEPOINT denied');}
}
try {
 await db.exec(await read('0001_baseline.sql')); await db.exec(await read('0002_portal.sql'));
 await db.exec(await read('0003_dispatch.sql'));
 await db.exec("CREATE TABLE public.alembic_version(version_num text); INSERT INTO public.alembic_version VALUES('0003_dispatch')");
 const name=(await db.query('SELECT current_database() n')).rows[0].n;
 await db.exec((await read('worker_grants.sql')).replace('CONNECT ON DATABASE sahayak','CONNECT ON DATABASE '+name));
 const employee='10000000-0000-4000-8000-000000000001';
 await db.exec('BEGIN');
 await db.query("INSERT INTO sahayak.profiles(id,identity_issuer,identity_subject,employee_code,display_name,email,phone_e164,phone_trusted_at,phone_trusted_by,phone_trust_method) VALUES($1,'test','worker','worker','Fixture','fixture@example.invalid','+919999999999',now(),'test','fixture')",[employee]);
 await db.query("INSERT INTO sahayak.profile_roles VALUES($1,'employee')",[employee]);
 await db.query("SELECT set_config('sahayak.actor_id',$1,true),set_config('sahayak.actor_kind','employee',true),set_config('sahayak.reason','Worker fixture',true)",[employee]);
 const create="INSERT INTO sahayak.tickets(employee_id,request_key,category,description,priority,callback_at) VALUES($1,gen_random_uuid(),'vpn','Fixture','medium',$2) RETURNING id";
 const ticket=(await db.query(create,[employee,null])).rows[0].id;
 await db.query(create,[employee,new Date(Date.now()+86400000).toISOString()]);
 await db.exec('SET LOCAL ROLE sahayak_dispatch');
 const claim=async token=>(await run(sql.claim[0],{limit:8,token,seconds:120})).rows[0];
 const first=await claim('lease-a'); assert.equal(first.ticket_id,ticket); checks++;
 assert.equal(await claim('lease-b'),undefined); checks++; // leased + future stay untouched
 await deny("UPDATE sahayak.tickets SET status='completed'");
 await deny('SELECT * FROM sahayak.profiles');
 await deny('DELETE FROM sahayak.outbox_events');
 await run(sql.failed[0],{...first,lease:'lease-a'});
 assert.equal(await claim('lease-b'),undefined); checks++; // backoff
 await db.exec('RESET ROLE'); await db.query("UPDATE sahayak.outbox_events SET lease_until=now()-interval '1 second' WHERE id=$1",[first.id]);
 await db.exec('SET LOCAL ROLE sahayak_dispatch');
 const second=await claim('lease-b'); assert.equal(first.id,second.id); checks++;
 assert.equal((await run(sql.published[0],{...first,lease:'lease-a'})).affectedRows,0); checks++; // fencing
 const context=(await run(sql.consume.find(q=>q.includes('dispatch_context')),{id:first.id})).rows[0];
 assert.equal(context.contact_ready,true); assert.equal(context.status,'new'); assert.equal(context.event_generation,1); checks++;
 const receipt=sql.consume.find(q=>q.includes('INSERT INTO'));
 await db.exec('SAVEPOINT crash');
 await run(receipt,{id:first.id,ticket,generation:1,result:'ready_calls_disabled'});
 await db.exec('ROLLBACK TO SAVEPOINT crash; RELEASE SAVEPOINT crash');
 assert.equal((await run(sql.consume.find(q=>q.startsWith('SELECT result')),{id:first.id})).rows.length,0); checks++;
 await run(receipt,{id:first.id,ticket,generation:1,result:'ready_calls_disabled'});
 assert.equal((await run(sql.consume.find(q=>q.startsWith('SELECT result')),{id:first.id})).rows[0].result,'ready_calls_disabled'); checks++;
 await deny("UPDATE sahayak.dispatch_preflights SET result='skipped_test'");
 assert.equal((await run(sql.published[0],{...second,lease:'lease-b'})).affectedRows,1); checks++;
 assert.equal((await run(sql.replay[0],{id:first.id})).affectedRows,0); checks++; // completed receipt cannot replay
 const status=(await run(sql.status[0],{limit:8})).rows[0]; assert.equal(Number(status.future),1); assert.equal(Number(status.published),1); checks++;
 await db.exec('RESET ROLE');
 assert.equal((await db.query('SELECT status FROM sahayak.tickets WHERE id=$1',[ticket])).rows[0].status,'new');
 assert.equal((await db.query('SELECT count(*) n FROM sahayak.call_attempts')).rows[0].n,0); checks++;
 // Exhausted sends need an explicit bounded retry; no hidden infinite loop.
 await db.exec("UPDATE sahayak.outbox_events SET available_at=now(),publish_attempts=8,lease_until=NULL WHERE published_at IS NULL; SET LOCAL ROLE sahayak_dispatch");
 assert.equal(await claim('lease-c'),undefined); checks++;
 const exhausted=(await db.query('SELECT id FROM sahayak.outbox_events WHERE published_at IS NULL')).rows[0].id;
 assert.equal((await run(sql.retry[0],{id:exhausted,limit:8})).affectedRows,1); checks++;
 const last=await claim('lease-c'); assert.equal(last.id,exhausted); checks++;
 await run(sql.published[0],{...last,lease:'lease-c'});
 assert.equal((await run(sql.replay[0],{id:exhausted})).affectedRows,1); checks++;
 assert.equal((await claim('lease-d')).id,exhausted); checks++; // same identity after explicit recovery
 const futureContext=(await run(sql.consume.find(q=>q.includes('dispatch_context')),{id:exhausted})).rows[0];
 assert.ok(new Date(futureContext.callback_at)>new Date(futureContext.database_now)); checks++;
 await db.exec('RESET ROLE');
 await db.query('UPDATE sahayak.profiles SET active=false WHERE id=$1',[employee]);
 await db.exec('SET LOCAL ROLE sahayak_dispatch');
 assert.equal((await run(sql.consume.find(q=>q.includes('dispatch_context')),{id:first.id})).rows[0].contact_ready,false); checks++;
 await db.exec('RESET ROLE; ROLLBACK');
 assert.equal((await db.query('SELECT count(*) n FROM sahayak.dispatch_preflights')).rows[0].n,0); checks++;
 console.log(`PASS: ${checks} worker SQL, lease recovery, fencing, rollback and privilege checks. No RDS/AWS access.`);
} catch(e) {console.error(e.message,e.code??'');process.exitCode=1;} finally{await db.close();}
