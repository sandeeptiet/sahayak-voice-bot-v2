"""SQS is a transport, never the source of employee or ticket authority."""
import json
import boto3
from botocore.config import Config

class SqsQueue:
    def __init__(self, settings, client=None):
        if not settings.queue_url: raise ValueError("Configure SAHAYAK_QUEUE_URL first")
        self.url=settings.queue_url
        self.client=client or boto3.Session(profile_name=settings.aws_profile,region_name=settings.aws_region).client(
            'sqs',config=Config(connect_timeout=5,read_timeout=25,retries={'mode':'standard','total_max_attempts':2}))

    def check(self):
        attrs=self.client.get_queue_attributes(QueueUrl=self.url,
            AttributeNames=['RedrivePolicy','QueueArn','SqsManagedSseEnabled','KmsMasterKeyId']).get('Attributes',{})
        policy=json.loads(attrs.get('RedrivePolicy','{}'))
        if not policy.get('deadLetterTargetArn') or not 1 <= int(policy.get('maxReceiveCount',0)) <= 10:
            raise ValueError("Queue requires a dead-letter policy with 1–10 receives")
        if attrs.get('SqsManagedSseEnabled')!='true' and not attrs.get('KmsMasterKeyId'):
            raise ValueError("Queue encryption must be enabled")

    def send(self, envelope):
        return self.client.send_message(QueueUrl=self.url,MessageBody=json.dumps(envelope))['MessageId']

    def receive(self):
        return self.client.receive_message(QueueUrl=self.url,MaxNumberOfMessages=1,
            WaitTimeSeconds=10,VisibilityTimeout=120).get('Messages',[])

    def delete(self, handle):
        self.client.delete_message(QueueUrl=self.url,ReceiptHandle=handle)

    def defer(self, handle):
        self.client.change_message_visibility(QueueUrl=self.url,ReceiptHandle=handle,VisibilityTimeout=60)
