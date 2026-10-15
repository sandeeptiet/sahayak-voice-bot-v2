"""Optional DeepEval runner over ONE saved synthetic report; no hidden default judge."""
import argparse
import asyncio
import json
import os
from pathlib import Path

# Standalone metrics only; no Confident AI uploads or telemetry.
os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'] = 'YES'
os.environ['DEEPEVAL_DISABLE_DOTENV'] = '1'
os.environ['CONFIDENT_METRIC_LOGGING_ENABLED'] = '0'

from deepeval.models import DeepEvalBaseLLM
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from pydantic import ValidationError
import httpx
from .config import AgentSettings
from .providers import Sarvam, ProviderError


class SarvamJudge(DeepEvalBaseLLM):
    def __init__(self, provider, model, max_calls=4):
        self.provider = provider
        self.calls = 0
        self.max_calls = max_calls
        super().__init__(model=model)

    def load_model(self):
        return self.provider

    def get_model_name(self):
        return self.name

    def generate(self, prompt, schema=None):
        if self.calls >= self.max_calls:
            raise ProviderError('Evaluation judge call budget exhausted')
        self.calls += 1
        format_note = 'Return only valid JSON, without markdown fences.'
        if schema is not None:
            format_note += ' Match this JSON schema: ' + json.dumps(schema.model_json_schema())
        data = self.provider.post('/v1/chat/completions', {
            'model': self.name,
            'messages': [{'role':'system', 'content':format_note}, {'role':'user', 'content':prompt}],
            'reasoning_effort': None, 'max_tokens': 1500, 'stream': False,
        })
        try:
            choice = data['choices'][0]
            if choice['finish_reason'] != 'stop':
                raise ValueError()
            text = choice['message']['content']
            return schema.model_validate_json(text) if schema is not None else text
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise ProviderError('Judge returned invalid/incomplete structured output; no score claimed') from None

    async def a_generate(self, prompt, schema=None):
        return await asyncio.to_thread(self.generate, prompt, schema)


def main():
    parser=argparse.ArgumentParser(description='Usage-billed DeepEval scores for one synthetic report')
    parser.add_argument('report', type=Path)
    parser.add_argument('--judge-model', default='sarvam-105b-conversations')
    args=parser.parse_args()
    record=json.loads(args.report.read_text())
    if record.get('mode') != 'synthetic_pilot' or record.get('status') != 'generated_unreviewed':
        raise SystemExit('Requires a generated synthetic demo report')
    output=args.report.with_suffix('.deepeval.json')
    if output.exists():
        raise SystemExit('Evaluation file already exists; no calls made')
    case=LLMTestCase(input=record['question'], actual_output=record['answer'],
                     retrieval_context=[s['text'] for s in record['sources']])
    settings=AgentSettings()
    with httpx.Client(follow_redirects=False) as http:
        judge=SarvamJudge(Sarvam(settings,http),args.judge_model)
        definitions=[
            ('Grounding', [
                'Compare factual claims in the answer against the retrieved context.',
                'Penalize unsupported repairs, invented policy, and claiming a workaround is resolution.',
                'An appropriate refusal when the context lacks an answer is correct.',
            ]),
            ('Employee response', [
                f'The requested language is {record["language"]}. Check compliance, allowing product names.',
                'Check that the answer addresses the question without unrelated scenarios or products.',
                'Penalize internal operator instructions, unnecessary jargon, and claims that actions were executed.',
            ]),
        ]
        scores=[]
        try:
            for name,steps in definitions:
                metric=GEval(name=name,evaluation_steps=steps,
                    evaluation_params=[LLMTestCaseParams.INPUT,LLMTestCaseParams.ACTUAL_OUTPUT,
                                       LLMTestCaseParams.RETRIEVAL_CONTEXT],
                    model=judge,async_mode=False)
                metric.measure(case)
                scores.append({'metric':name,'score':metric.score,'reason':metric.reason})
        except Exception as exc:
            # Deliberately suppress raw judge/provider response bodies.
            raise SystemExit(f'Evaluation incomplete ({type(exc).__name__}); no passing result claimed') from None
    report={'framework':'deepeval==3.8.9','judge':args.judge_model,'calls':judge.calls,
            'advisory_only':True,'release_thresholds_approved':False,
            'limitations':'Same-provider judge may share generator biases; human review still required.',
            'scores':scores}
    with output.open('x') as handle:json.dump(report,handle,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('Evaluation:',output)

if __name__=='__main__':main()
