"""Offline worker delivery/recovery and deterministic graph tests. No AWS/RDS."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from pydantic import ValidationError
from sahayak.dispatch.config import WorkerSettings
from sahayak.dispatch.worker import Worker, Envelope
from sahayak.dispatch.workflow import workflow
from sahayak.dispatch.store import Store
from sahayak.dispatch.queue import SqsQueue

NOW=datetime.now(timezone.utc)

def context(**overrides):
    return dict(status='new',assigned=False,is_test=False,contact_ready=True,
        event_generation=1,current_generation=1,available_at=NOW,callback_at=None,
        database_now=NOW,**{}) | overrides

@pytest.mark.parametrize('changes,expected',[
    ({},'ready_calls_disabled'),({'is_test':True},'skipped_test'),
    ({'current_generation':2},'skipped_generation'),
    ({'status':'cancelled'},'skipped_state'),({'status':'completed'},'skipped_state'),
    ({'status':'failed'},'skipped_state'),({'status':'in_progress'},'skipped_state'),
    ({'status':'transferred_to_human'},'skipped_state'),({'assigned':True},'skipped_assignment'),
    ({'contact_ready':False},'skipped_contact'),
    ({'available_at':NOW+timedelta(days=1)},'deferred'),
    ({'callback_at':NOW+timedelta(minutes=1)},'deferred'),
])
def test_preflight_never_advances_lifecycle(changes,expected):
    state=context(**changes)
    result=workflow.invoke(state)
    assert result['result']==expected
    assert result['status']==state['status']

@pytest.mark.parametrize('settings',[
    {'outbound_calls_enabled':True},{'worker_mode':'live'},
    {'queue_url':'https://attacker.invalid/queue'},
    {'queue_url':'https://sqs.ap-south-1.amazonaws.com/123456789012/a.fifo'},
    {'max_publish_attempts':0},{'lease_seconds':10},
])
def test_configuration_fails_closed(settings):
    with pytest.raises(ValidationError): WorkerSettings(_env_file=None,**settings)

@pytest.fixture
def worker():
    store=Mock(); queue=Mock()
    store.claim.return_value={'id':uuid4(),'ticket_id':uuid4(),'schedule_generation':1,'lease':str(uuid4())}
    settings=SimpleNamespace(max_publish_attempts=8,lease_seconds=120)
    return Worker(store,queue,settings)

def message(worker):
    e=worker.store.claim.return_value
    body=Envelope(schema_version=1,mode='preflight',event_id=e['id'],ticket_id=e['ticket_id'],schedule_generation=1)
    worker.queue.receive.return_value=[{'Body':body.model_dump_json(),'ReceiptHandle':'current-handle'}]
    return body

def test_send_failure_retains_work(worker):
    worker.queue.send.side_effect=TimeoutError('potentially accepted by SQS')
    assert worker.publish_one()=='retry'
    worker.store.failed.assert_called_once()
    worker.store.published.assert_not_called()

def test_send_then_commit_failure_reuses_identity(worker):
    worker.store.published.side_effect=[RuntimeError('db disconnected'),True]
    with pytest.raises(RuntimeError): worker.publish_one()
    assert worker.publish_one()=='published'
    bodies=[call.args[0] for call in worker.queue.send.call_args_list]
    assert bodies[0]==bodies[1]
    assert set(bodies[0])=={'schema_version','mode','event_id','ticket_id','schedule_generation'}

def test_stale_sender_reports_lost_lease(worker):
    worker.store.published.return_value=False
    assert worker.publish_one()=='lease_lost'

def test_database_failure_does_not_delete_message(worker):
    message(worker); worker.store.consume.side_effect=RuntimeError('rollback')
    with pytest.raises(RuntimeError): worker.consume_one()
    worker.queue.delete.assert_not_called()

def test_delete_failure_replays_receipt_without_repeating_work(worker):
    message(worker); worker.store.consume.side_effect=['ready_calls_disabled','duplicate']
    worker.queue.delete.side_effect=[TimeoutError(),None]
    with pytest.raises(TimeoutError): worker.consume_one()
    assert worker.consume_one()=='duplicate'
    assert worker.queue.delete.call_count==2

def test_early_delivery_is_deferred(worker):
    message(worker); worker.store.consume.return_value='deferred'
    assert worker.consume_one()=='deferred'
    worker.queue.defer.assert_called_once_with('current-handle')
    worker.queue.delete.assert_not_called()

@pytest.mark.parametrize('body',['not json','{}',json.dumps({'phone':'+919999999999'}),'x'*2049])
def test_malformed_messages_left_for_dlq(worker,body):
    worker.queue.receive.return_value=[{'Body':body,'ReceiptHandle':'h'}]
    assert worker.consume_one()=='invalid'
    worker.store.consume.assert_not_called(); worker.queue.delete.assert_not_called()

def test_forged_event_not_acknowledged(worker):
    message(worker); worker.store.consume.return_value='invalid'
    assert worker.consume_one()=='invalid'; worker.queue.delete.assert_not_called()

def test_queue_visibility_and_receipt_contract():
    client=Mock(); settings=WorkerSettings(_env_file=None,queue_url='https://sqs.ap-south-1.amazonaws.com/123456789012/test')
    queue=SqsQueue(settings,client)
    client.receive_message.return_value={'Messages':[]}
    assert queue.receive()==[]
    assert client.receive_message.call_args.kwargs['MaxNumberOfMessages']==1
    assert client.receive_message.call_args.kwargs['WaitTimeSeconds']==10
    queue.delete('latest'); assert client.delete_message.call_args.kwargs['ReceiptHandle']=='latest'
    client.get_queue_attributes.return_value={'Attributes':{'SqsManagedSseEnabled':'true','RedrivePolicy':json.dumps({'deadLetterTargetArn':'arn:test','maxReceiveCount':5})}}
    queue.check()
    client.get_queue_attributes.return_value={'Attributes':{}}
    with pytest.raises(ValueError): queue.check()


def test_worker_loads_setup_generated_dotenv(tmp_path):
    path=tmp_path/'worker.env'
    path.write_text('SAHAYAK_WORKER_MODE="preflight"\nSAHAYAK_OUTBOUND_CALLS_ENABLED="false"\n')
    settings=WorkerSettings(_env_file=path)
    assert settings.outbound_calls_enabled is False

@pytest.mark.parametrize('value',['true','1','yes',True,1,0,'',None])
def test_call_switch_never_accepts_enabled_or_ambiguous_values(value):
    with pytest.raises(ValidationError):
        WorkerSettings(_env_file=None,outbound_calls_enabled=value)
