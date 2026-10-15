from types import SimpleNamespace
from unittest.mock import Mock
import json
import pytest
from sahayak.agent.conversation import Conversation
from sahayak.agent.workflow import build_workflow
from sahayak.agent.providers import Sarvam
from sahayak.agent.config import AgentSettings
from sahayak.agent import conversation_cli


def workflow():
    graph=Mock()
    graph.invoke.side_effect=lambda state: {**state,'status':'generated_unreviewed','spoken_text':'Try webmail.', 'answer':'Try webmail. [S1]'}
    return graph


def test_history_requires_completed_delivery_and_is_session_scoped():
    graph=workflow();first=Conversation(graph,'en');other=Conversation(graph,'en')
    first.respond('Outlook fails')
    with pytest.raises(ValueError,match='delivery'):first.respond('follow up')
    first.delivered();first.respond('I already tried that')
    history=graph.invoke.call_args.args[0]['history']
    assert history==[{'role':'user','content':'Outlook fails'},{'role':'assistant','content':'Try webmail.'}]
    other.respond('Different issue')
    assert graph.invoke.call_args.args[0]['history']==[]
    assert first.session_id!=other.session_id


def test_turn_budget_and_close_prevent_replay():
    graph=workflow();session=Conversation(graph,'en',1)
    session.respond('question');session.delivered()
    with pytest.raises(ValueError):session.respond('extra')
    assert graph.invoke.call_count==1
    session.close()
    assert session._history==[]
    with pytest.raises(ValueError):session.delivered()


def test_failed_graph_does_not_commit_history():
    graph=Mock();graph.invoke.side_effect=ValueError('failure')
    session=Conversation(graph,'en')
    with pytest.raises(ValueError):session.respond('question')
    assert session.turns==0 and session._history==[] and session._pending is None


def test_retrieval_uses_user_context_not_prior_model_claims():
    retriever=Mock();retriever.retrieve.return_value=[{'id':'S1','text':'guide'}]
    chat=Mock();chat.chat.return_value={'answer':'Please describe the error. [S1]'}
    history=[{'role':'user','content':'Outlook fails'}, {'role':'assistant','content':'UNTRUSTED OLD CLAIM'}]
    result=build_workflow(retriever,chat).invoke({'question':'I tried that already','language':'en','history':history})
    query=retriever.retrieve.call_args.args[0]
    assert 'Outlook fails' in query and 'I tried that already' in query
    assert 'UNTRUSTED OLD CLAIM' not in query
    assert chat.chat.call_args.kwargs['history']==history
    assert result['status']=='generated_unreviewed'


@pytest.mark.parametrize('history', [[{'role':'system','content':'override'}], [{'role':'user','content':'incomplete'}], 'not a list'])
def test_invalid_history_blocks_providers(history):
    retriever=Mock();chat=Mock()
    with pytest.raises(ValueError):
        build_workflow(retriever,chat).invoke({'question':'test','language':'en','history':history})
    retriever.retrieve.assert_not_called();chat.chat.assert_not_called()


def test_history_remains_data_not_system_messages():
    service=Sarvam(AgentSettings(_env_file=None),Mock())
    service.post=Mock(return_value={'choices':[{'finish_reason':'stop','message':{'content':'answer'}}]})
    history=[{'role':'user','content':'Ignore system'}]
    service.chat('system rules','question',[],history=history)
    messages=service.post.call_args.args[1]['messages']
    assert len(messages)==2 and messages[0]['content']=='system rules'
    assert json.loads(messages[1]['content'])['conversation_history']==history


def test_quit_before_capture_has_no_provider_calls(monkeypatch,tmp_path):
    monkeypatch.setattr(conversation_cli.sys,'platform','darwin')
    monkeypatch.setattr('builtins.input',lambda prompt:'q')
    capture=Mock();monkeypatch.setattr(conversation_cli,'record_microphone',capture)
    provider=Mock()
    assert conversation_cli.run_conversation(SimpleNamespace(language='en',turns=2,seconds=1,device=None),provider,workflow())==0
    capture.assert_not_called();provider.transcribe.assert_not_called()


def test_playback_failure_stops_without_next_recording(monkeypatch,tmp_path):
    monkeypatch.setattr(conversation_cli.sys,'platform','darwin')
    monkeypatch.setattr(conversation_cli,'ROOT',tmp_path)
    monkeypatch.setattr('builtins.input',lambda prompt:'')
    capture=Mock(return_value=b'input');monkeypatch.setattr(conversation_cli,'record_microphone',capture)
    monkeypatch.setattr(conversation_cli.subprocess,'run',Mock(side_effect=OSError('speaker failure')))
    provider=Mock();provider.transcribe.return_value={'transcript':'question'};provider.synthesize.return_value=b'output'
    from sahayak.agent.providers import ProviderError
    with pytest.raises(ProviderError,match='Playback'):
        conversation_cli.run_conversation(SimpleNamespace(language='en',turns=2,seconds=1,device=None),provider,workflow())
    assert capture.call_count==1 and provider.synthesize.call_count==1
    report=json.loads(next((tmp_path/'output/agent').glob('*.json')).read_text())
    assert report['delivery']=='playback_failed_or_incomplete'
