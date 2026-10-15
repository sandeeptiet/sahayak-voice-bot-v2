"""Optional judge adapter contract checks; never call a live provider."""
import os
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
os.environ['DEEPEVAL_DISABLE_DOTENV'] = '1'
import pytest
pytest.importorskip('deepeval')
from pydantic import BaseModel
from sahayak.agent.evaluation import SarvamJudge
from sahayak.agent.providers import ProviderError

class Score(BaseModel):
    score: int

class Provider:
    def __init__(self, content='{"score": 8}'):
        self.content = content
        self.requests = []
    def post(self, path, payload):
        self.requests.append(payload)
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': self.content}}]}

def test_judge_schema_model_and_budget():
    provider = Provider()
    judge = SarvamJudge(provider, 'sarvam-105b-conversations', max_calls=1)
    assert judge.get_model_name() == 'sarvam-105b-conversations'
    assert judge.generate('synthetic prompt', schema=Score).score == 8
    assert provider.requests[0]['model'] == 'sarvam-105b-conversations'
    with pytest.raises(ProviderError, match='budget'):
        judge.generate('another prompt', schema=Score)
    assert len(provider.requests) == 1

def test_invalid_judge_output_does_not_become_score():
    provider = Provider('not json')
    judge = SarvamJudge(provider, 'sarvam-105b-conversations')
    with pytest.raises(ProviderError, match='no score claimed'):
        judge.generate('synthetic prompt', schema=Score)
    assert len(provider.requests) == 1
