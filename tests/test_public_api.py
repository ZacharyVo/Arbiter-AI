from fastapi.testclient import TestClient


def test_new_facade_exports_public_sdk():
    import pluralforge as p
    assert p.__version__=='0.5.0'
    assert p.select_next_action is not None


def test_route_http_endpoint():
    from arbiter_plugin.api import create_app
    client=TestClient(create_app())
    result=client.post('/v1/next-step',json={
      'forecasts':[{'action':'consult_agent','agent_id':'alpha',
       'expected_decision_gain':9,'execution_cost_utility':2,
       'estimated_api_cost_usd':.01,'rationale':'host forecast'}],
      'remaining_api_budget_usd':.1,
      'agent_reservations_usd':{'alpha':.02},
    })
    assert result.status_code==200 and result.json()['action']=='consult_agent'
    assert result.json()['predicted_net_gain']==7


def test_route_http_invalid_unknown_agent():
    from arbiter_plugin.api import create_app
    client=TestClient(create_app())
    result=client.post('/v1/next-step',json={
      'forecasts':[{'action':'consult_agent','agent_id':'ghost',
       'expected_decision_gain':9,'execution_cost_utility':2,
       'estimated_api_cost_usd':0,'rationale':'host forecast'}],
      'remaining_api_budget_usd':.1,
      'agent_reservations_usd':{'alpha':.02}})
    assert result.status_code==200 and result.json()['action']=='stop'
