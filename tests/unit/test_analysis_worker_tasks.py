from app.config import Settings
from app.services.analysis_worker_tasks import AnalysisWorkerTaskClient


def test_analysis_worker_task_client_is_disabled_without_queue_config():
    settings = Settings(
        gcp_project_id="",
        gcp_region="asia-southeast1",
        analysis_worker_tasks_queue="",
        analysis_worker_url="",
    )
    client = AnalysisWorkerTaskClient(settings=settings)

    assert client.is_configured() is False
    assert client.enqueue_drain(reason="unit-test") is False


def test_analysis_worker_task_client_builds_worker_drain_url():
    settings = Settings(
        gcp_project_id="sushi-d9036",
        gcp_region="asia-southeast1",
        analysis_worker_tasks_queue="analysis-worker",
        analysis_worker_url="https://worker.example.run.app/",
        analysis_worker_drain_path="/internal/analysis-worker/drain",
    )
    client = AnalysisWorkerTaskClient(settings=settings)

    assert client.is_configured() is True
    assert client._worker_drain_url() == "https://worker.example.run.app/internal/analysis-worker/drain"


def test_analysis_worker_task_client_builds_authenticated_http_request():
    class FakeOidcToken:
        service_account_email = ""
        audience = ""

    class FakeHttpRequest:
        def __init__(self, *, http_method, url, headers, body):
            self.http_method = http_method
            self.url = url
            self.headers = headers
            self.body = body
            self.oidc_token = FakeOidcToken()

    class FakeHttpMethod:
        POST = "POST"

    class FakeTasksV2:
        HttpMethod = FakeHttpMethod
        HttpRequest = FakeHttpRequest

    settings = Settings(
        gcp_project_id="sushi-d9036",
        gcp_region="asia-southeast1",
        analysis_worker_tasks_queue="analysis-worker",
        analysis_worker_url="https://worker.example.run.app",
        analysis_worker_task_service_account_email="worker-invoker@example.iam.gserviceaccount.com",
        analysis_worker_internal_token="unit-token",
    )
    client = AnalysisWorkerTaskClient(settings=settings)

    request = client._build_http_request(tasks_v2=FakeTasksV2, reason="analysis_batch:123")

    assert request.http_method == "POST"
    assert request.url == "https://worker.example.run.app/internal/analysis-worker/drain"
    assert request.headers["X-Sushi-Worker-Token"] == "unit-token"
    assert request.body == b'{"reason": "analysis_batch:123"}'
    assert request.oidc_token.service_account_email == "worker-invoker@example.iam.gserviceaccount.com"
    assert request.oidc_token.audience == "https://worker.example.run.app"
