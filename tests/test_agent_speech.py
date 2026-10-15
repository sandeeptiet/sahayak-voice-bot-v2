import io
import wave
from unittest.mock import Mock
import httpx
import pytest
from sahayak.agent.config import AgentSettings
from sahayak.agent.providers import Sarvam, ProviderError
from sahayak.agent.speech import validate_recording, read_recording, run_spoken_turn


def recording(seconds=1, channels=1):
    buf=io.BytesIO()
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b'\x00\x00' * int(16000*seconds) * channels)
    return buf.getvalue()


def provider(handler):
    return Sarvam(AgentSettings(_env_file=None, SARVAM_API_KEY='test-key'),
                  httpx.Client(transport=httpx.MockTransport(handler)))


def test_stt_multipart_contract():
    def handler(request):
        assert request.url.path == '/speech-to-text'
        assert request.headers['content-type'].startswith('multipart/form-data')
        body=request.content
        for expected in (b'saaras:v3', b'transcribe', b'hi-IN', b'utterance.wav', b'audio/wav', b'RIFF'):
            assert expected in body
        return httpx.Response(200,json={'transcript':' Outlook नहीं चल रहा। ', 'language_code':'hi-IN'})
    result=provider(handler).transcribe(recording(), 'hinglish')
    assert result['transcript']=='Outlook नहीं चल रहा।'


@pytest.mark.parametrize('audio', [b'bad', recording(30), recording(0), recording(channels=2), recording()[:-5], b'x'*3_000_001])
def test_invalid_recording_never_uploaded(audio):
    client=Mock()
    with pytest.raises(ValueError):
        Sarvam(AgentSettings(_env_file=None),client).transcribe(audio,'hi')
    client.post.assert_not_called()


@pytest.mark.parametrize('result', [{}, [], {'transcript':''}, {'transcript':' '*5},
    {'transcript':'a'*2001,'language_code':'en-IN'}, {'transcript':'hello','language_code':None},
    {'transcript':'hello','language_code':'fr-FR'}])
def test_bad_transcripts_block_processing(result):
    with pytest.raises(ProviderError):
        provider(lambda r:httpx.Response(200,json=result)).transcribe(recording(),'en')


def test_stt_failure_does_not_run_reasoning_or_speech():
    service=Mock();service.transcribe.side_effect=ProviderError('failure')
    workflow=Mock()
    with pytest.raises(ProviderError):
        run_spoken_turn(recording(),'en',service,workflow)
    workflow.invoke.assert_not_called();service.synthesize.assert_not_called()


def test_spoken_turn_uses_transcript_and_requested_language():
    service=Mock();service.transcribe.return_value={'transcript':'VPN fails'}
    service.synthesize.return_value=b'reply'
    workflow=Mock();workflow.invoke.return_value={'status':'generated_unreviewed','spoken_text':'Please describe the error.'}
    state,audio=run_spoken_turn(recording(),'en',service,workflow)
    workflow.invoke.assert_called_once_with({'question':'VPN fails','language':'en'})
    assert state['transcription']['transcript']=='VPN fails' and audio==b'reply'


def test_no_evidence_does_not_synthesize():
    service=Mock();service.transcribe.return_value={'transcript':'question'}
    workflow=Mock();workflow.invoke.return_value={'status':'no_evidence'}
    _,audio=run_spoken_turn(recording(),'en',service,workflow)
    assert audio is None
    service.synthesize.assert_not_called()


def test_upload_error_is_redacted_and_not_retried():
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(503,text='private transcript test-key')
    with pytest.raises(ProviderError) as exc:
        provider(handler).transcribe(recording(),'hi')
    assert len(calls)==1 and 'private' not in str(exc.value) and 'test-key' not in str(exc.value)


def test_missing_recording_has_safe_error(tmp_path):
    with pytest.raises(ValueError,match='Cannot read'):
        read_recording(tmp_path/'missing.wav')
