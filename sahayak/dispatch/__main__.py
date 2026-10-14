"""Bounded by default: status, publish, consume, or explicit continuous run."""
import argparse
import json
import logging
import time
from uuid import UUID
from pydantic import ValidationError
from .config import WorkerSettings
from .store import Store
from .queue import SqsQueue
from .worker import Worker

def main():
    parser=argparse.ArgumentParser(description='Sahayak calls-disabled dispatch worker')
    parser.add_argument('command',choices=['status','publish','consume','run','retry','replay'])
    parser.add_argument('--loop',action='store_true',help='Continue run until Ctrl-C; calls stay disabled')
    parser.add_argument('--event-id',type=UUID)
    args=parser.parse_args()
    if args.loop and args.command!='run': parser.error('--loop is only valid with run')
    if args.command in ('retry','replay') and not args.event_id: parser.error('recovery requires --event-id')
    engine=None
    try:
        settings=WorkerSettings(); engine=settings.engine(); store=Store(engine); store.check()
        if args.command=='status': print(json.dumps(store.status(settings.max_publish_attempts))); return
        if args.command=='retry':
            print('retry_scheduled' if store.retry(args.event_id,settings.max_publish_attempts) else 'not_eligible'); return
        if args.command=='replay':
            print('replay_scheduled' if store.replay(args.event_id) else 'not_eligible'); return
        queue=SqsQueue(settings); queue.check(); worker=Worker(store,queue,settings)
        print('Mode: preflight. No model requests or phone calls. Ticket statuses stay unchanged.',flush=True)
        while True:
            try:
                if args.command in ('publish','run'): print('publisher:',worker.publish_one(),flush=True)
                if args.command in ('consume','run'): print('consumer:',worker.consume_one(),flush=True)
            except Exception:
                # A failed DB commit or queue delete is retried on redelivery.
                print('worker_cycle_failed: check database/queue access; message not acknowledged.',flush=True)
                if not args.loop: raise SystemExit(1) from None
            if not args.loop: break
            time.sleep(settings.poll_seconds)
    except KeyboardInterrupt: print('Worker stopped. Leases and unacknowledged messages can recover.')
    except ValidationError as error:
        fields=", ".join(".".join(map(str,item["loc"])) for item in error.errors(include_input=False,include_context=False))
        print(f"Worker configuration invalid: {fields}. No values or secrets printed.")
        raise SystemExit(1) from None
    except Exception:
        print('Worker setup failed. Check .env.worker, migration, AWS login, queue permissions and DLQ. No secrets printed.')
        raise SystemExit(1) from None
    finally:
        if engine is not None: engine.dispose()

if __name__=='__main__':
    logging.basicConfig(level=logging.WARNING)
    main()
