import asyncio
import json
import sys
import types
from arbiter_plugin import Option, DecisionRequest
from arbiter_plugin.llm_adapters import AgentSpec, ask_one, ask_parallel


def req():
    return DecisionRequest(decision_id='x', objective='decide', mode='consensus',
                           options=[Option(id='a'),Option(id='b')])


def fake_response(payload):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content=json.dumps(payload)))])


def test_live_adapter_labels_are_validated(monkeypatch):
    async def generate(**kwargs):
        return fake_response({'option_id':'nonexistent','confidence':0.9})
    monkeypatch.setitem(sys.modules, 'litellm', types.SimpleNamespace(acompletion=generate,
                         completion_cost=lambda **kwargs:.01))
    try:
        asyncio.run(ask_one(req(),AgentSpec('a','mock-model')))
    except ValueError:
        pass
    else:
        raise AssertionError('Unexpected option should be rejected')


def test_parallel_model_adapter(monkeypatch):
    async def generate(**kwargs):
        return fake_response({'option_id':'b', 'confidence':.96, 'rationale':'A measured reason', 'evidence': []})
    monkeypatch.setitem(sys.modules, 'litellm', types.SimpleNamespace(acompletion=generate,
                         completion_cost=lambda **kwargs:.01))
    out=asyncio.run(ask_parallel(req(),[AgentSpec('x','model1'),AgentSpec('y','model2')]))
    assert len(out.opinions)==2
    assert out.total_cost_usd_estimate==.02
    assert all(x.confidence_source=='self_report' for x in out.opinions)
