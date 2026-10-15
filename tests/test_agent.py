import base64
import io
import json
import wave
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from sahayak.agent.config import AgentSettings
from sahayak.agent.providers import Sarvam, BedrockRetriever, ProviderError
from sahayak.agent.workflow import build_workflow, validate_answer, instructions


def settings():
    return AgentSettings(_env_file=None, SARVAM_API_KEY='secret-test-key')


def sarvam(handler):
    return Sarvam(settings(), httpx.Client(transport=httpx.MockTransport(handler)))


def wav_bytes(rate=24000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
        wav.writeframes(b'\x00\x00' * 240)
    return output.getvalue()


def test_tts_contract_and_audio_validation():
    data = wav_bytes()
    def handler(request):
        payload = json.loads(request.content)
        assert request.url.path == '/text-to-speech'
        assert payload['language_code'] == 'hi-IN'
        assert payload['model'] == 'bulbul:v3'
        assert payload['output_audio_codec'] == 'wav'
        assert 'target_language_code' not in payload
        return httpx.Response(200, json={'audios': [base64.b64encode(data).decode()]})
    assert sarvam(handler).synthesize('नमस्ते', 'hi') == data


@pytest.mark.parametrize('audios', [[], ['!!!'], [''], ['YQ=='], ['YQ==', 'YQ==']])
def test_invalid_audio_never_released(audios):
    with pytest.raises(ProviderError):
        sarvam(lambda r: httpx.Response(200, json={'audios': audios})).synthesize('hello', 'en')


def test_audio_rate_mismatch_rejected():
    with pytest.raises(ProviderError):
        sarvam(lambda r: httpx.Response(200, json={'audios': [base64.b64encode(wav_bytes(16000)).decode()]})).synthesize('hello', 'en')


@pytest.mark.parametrize('text,language', [('', 'en'), ('a'*2501, 'en'), ('hi', 'unknown')])
def test_tts_invalid_input_has_no_network_call(text, language):
    client = Mock()
    with pytest.raises(ValueError):
        Sarvam(settings(), client).synthesize(text, language)
    client.post.assert_not_called()


def test_provider_error_is_redacted_and_not_retried():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429, text='secret-test-key private provider details')
    with pytest.raises(ProviderError) as error:
        sarvam(handler).synthesize('hello', 'en')
    assert 'secret' not in str(error.value) and len(calls) == 1


@pytest.mark.parametrize('finish,answer', [('length', 'partial'), ('stop', ''), ('tool_calls', 'ok')])
def test_chat_rejects_incomplete_output(finish, answer):
    provider=sarvam(lambda r: httpx.Response(200, json={'choices': [{'finish_reason': finish, 'message': {'content': answer}}]}))
    with pytest.raises(ProviderError):
        provider.chat('system', 'question', [])


def test_retrieval_scope_rejects_unexpected_bucket():
    client=Mock()
    client.retrieve.return_value={'retrievalResults': [{'location': {'s3Location': {'uri': 's3://other/private.pdf'}}, 'content': {'text': 'secret'}}]}
    with pytest.raises(ProviderError, match='outside'):
        BedrockRetriever(client, settings()).retrieve('question')


def test_no_evidence_skips_model():
    retriever=Mock();retriever.retrieve.return_value=[]
    chat=Mock()
    result=build_workflow(retriever, chat).invoke({'question': 'test', 'language':'en'})
    assert result['status']=='no_evidence'
    chat.chat.assert_not_called()


def test_retrieval_failure_skips_model():
    retriever=Mock();retriever.retrieve.side_effect=ProviderError('unavailable')
    chat=Mock()
    with pytest.raises(ProviderError):
        build_workflow(retriever, chat).invoke({'question': 'test', 'language':'en'})
    chat.chat.assert_not_called()


def test_graph_preserves_evidence_and_marks_unreviewed():
    sources=[{'id':'S1','uri':'s3://pilot/a.pdf','text':'webmail is a workaround'}]
    retriever=Mock();retriever.retrieve.return_value=sources
    chat=Mock();chat.chat.return_value={'answer':'अभी समस्या हल नहीं हुई है। [S1]', 'usage':{'total_tokens':10}}
    result=build_workflow(retriever,chat).invoke({'question':'क्या समस्या हल हुई?', 'language':'hi'})
    assert result['status']=='generated_unreviewed'
    assert result['sources']==sources and '[S1]' not in result['spoken_text']
    assert result['answer'].endswith('[S1]')
    assert 'ticket_status' not in result


def test_wrong_language_and_unknown_citation_block_speech():
    sources=[{'id':'S1'}]
    with pytest.raises(ProviderError, match='Hindi'):
        validate_answer('English only [S1]', sources, 'hi')
    with pytest.raises(ProviderError, match='citation'):
        validate_answer('नमस्ते [S99]', sources, 'hi')


def test_prompt_language_is_parameterized_not_scenario_hardcoded():
    assert 'Devanagari' in instructions('hi')
    assert 'Latin script' in instructions('hinglish')
    assert 'webmail work' not in instructions('en')


def test_secret_is_hidden_in_config_repr():
    assert 'secret-test-key' not in repr(settings())
