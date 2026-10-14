import logging
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, ValidationError

log=logging.getLogger(__name__)

class Envelope(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version: Literal[1]
    mode: Literal['preflight']
    event_id: UUID
    ticket_id: UUID
    schedule_generation: int = Field(ge=1,strict=True)

class Worker:
    def __init__(self, store, queue, settings):
        self.store,self.queue,self.settings=store,queue,settings

    def publish_one(self):
        event=self.store.claim(self.settings.max_publish_attempts,self.settings.lease_seconds)
        if not event: return 'idle'
        envelope=Envelope(schema_version=1,mode='preflight',event_id=event['id'],
            ticket_id=event['ticket_id'],schedule_generation=event['schedule_generation'])
        try:
            self.queue.send(envelope.model_dump(mode='json'))
        except Exception:
            self.store.failed(event)
            log.warning('queue_send_failed event_id=%s',event['id'])
            return 'retry'
        # If this commit fails, the lease expires and the SAME event is sent again.
        return 'published' if self.store.published(event) else 'lease_lost'

    def consume_one(self):
        messages=self.queue.receive()
        if not messages: return 'idle'
        message=messages[0]
        try:
            if len(message['Body'])>2048: return 'invalid'
            envelope=Envelope.model_validate_json(message['Body'])
        except (ValidationError,KeyError,TypeError):
            log.warning('invalid_queue_envelope')
            return 'invalid'
        result=self.store.consume(envelope)
        if result=='deferred': self.queue.defer(message['ReceiptHandle'])
        elif result!='invalid': self.queue.delete(message['ReceiptHandle'])
        return result
