from xymphony_api.schemas import HealthResponse


def test_health_response_shape() -> None:
    body = HealthResponse(status="ok", database="connected")
    dumped = body.model_dump()
    assert dumped == {"status": "ok", "database": "connected"}
