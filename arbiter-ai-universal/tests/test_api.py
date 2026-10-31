from arbiter_plugin import DecisionRequest, Option
from arbiter_plugin.api import create_app

def test_fastapi_routes_if_installed():
    app=create_app()
    assert '/v1/evaluate' in [route.path for route in app.routes]
    assert '/v1/research' in [route.path for route in app.routes]
    assert '/v1/feedback' not in [route.path for route in app.routes]
