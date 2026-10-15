import io
import wave
from unittest.mock import Mock, MagicMock
import pytest
from sahayak.agent.microphone import record_microphone
from sahayak.agent import __main__ as cli


class AudioError(Exception):
    pass


def backend(overflow=False, silent=False):
    device=MagicMock()
    device.PortAudioError=AudioError
    device.query_devices.return_value={'default_samplerate':48000}
    stream=device.RawInputStream.return_value.__enter__.return_value
    stream.read.side_effect=lambda count: ((b'\x00\x00' if silent else b'\x01\x00')*count, overflow)
    return device


def test_capture_is_bounded_pcm_and_closes_device():
    device=backend()
    audio=record_microphone(1, backend=device)
    with wave.open(io.BytesIO(audio),'rb') as wav:
        assert wav.getnframes()==48000 and wav.getnchannels()==1
        assert wav.getsampwidth()==2
    device.RawInputStream.return_value.__exit__.assert_called_once()


@pytest.mark.parametrize('seconds',[0,26,-1,1.5])
def test_bad_duration_never_opens_microphone(seconds):
    device=backend()
    with pytest.raises(ValueError):record_microphone(seconds,backend=device)
    device.RawInputStream.assert_not_called()


@pytest.mark.parametrize('overflow,silent',[(True,False),(False,True)])
def test_bad_audio_is_discarded(overflow,silent):
    device=backend(overflow,silent)
    with pytest.raises(ValueError):record_microphone(1,backend=device)
    device.RawInputStream.return_value.__exit__.assert_called_once()


def test_permission_error_is_actionable():
    device=backend();device.query_devices.side_effect=AudioError('private device detail')
    with pytest.raises(ValueError,match='permission') as exc:record_microphone(1,backend=device)
    assert 'private' not in str(exc.value)


def test_interrupt_closes_input_stream():
    device=backend()
    device.RawInputStream.return_value.__enter__.return_value.read.side_effect=KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):record_microphone(1,backend=device)
    device.RawInputStream.return_value.__exit__.assert_called_once()


def test_cancel_at_prompt_never_records_or_calls_provider(monkeypatch):
    monkeypatch.setattr('sys.argv',['agent','microphone-demo'])
    monkeypatch.setattr(cli,'AgentSettings',lambda:Mock())
    def cancel(*args):raise KeyboardInterrupt
    monkeypatch.setattr('builtins.input',cancel)
    capture=Mock();http=Mock()
    monkeypatch.setattr(cli,'record_microphone',capture)
    monkeypatch.setattr(cli.httpx,'Client',http)
    assert cli.main()==130
    capture.assert_not_called();http.assert_not_called()


def test_capture_failure_never_calls_provider(monkeypatch):
    monkeypatch.setattr('sys.argv',['agent','microphone-demo'])
    monkeypatch.setattr(cli,'AgentSettings',lambda:Mock())
    monkeypatch.setattr('builtins.input',lambda *args:'')
    capture=Mock(side_effect=ValueError('Microphone unavailable'))
    http=Mock()
    monkeypatch.setattr(cli,'record_microphone',capture)
    monkeypatch.setattr(cli.httpx,'Client',http)
    assert cli.main()==1
    http.assert_not_called()
