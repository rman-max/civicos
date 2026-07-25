from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from civicos_api.auth import Principal, principal_headers
from civicos_api.config import Settings, cors_origin_strings
from civicos_api.main import app


def test_health_response_contains_request_id_and_security_headers() -> None:
    response = TestClient(app).get("/healthz", headers={"X-Request-ID": "request-123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_development_current_user_route_accepts_only_the_local_scaffold_headers() -> None:
    response = TestClient(app).get(
        "/v1/me",
        headers={
            "X-CivicOS-Organization-ID": "10000000-0000-0000-0000-000000000001",
            "X-CivicOS-User-ID": "20000000-0000-0000-0000-000000000001",
            "X-CivicOS-Role": "researcher",
        },
    )

    assert response.status_code == 200
    assert response.json()["role_key"] == "researcher"


def test_verified_principal_replaces_client_controlled_scope_headers() -> None:
    principal = Principal(
        user_id=UUID("20000000-0000-0000-0000-000000000001"),
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        role_key="tenant_admin",
        external_subject="oidc-admin",
    )
    headers = principal_headers(
        principal,
        [
            (b"x-civicos-organization-id", b"attacker-controlled"),
            (b"x-civicos-user-id", b"attacker-controlled"),
            (b"authorization", b"Bearer verified"),
        ],
    )

    values = {name: value for name, value in headers}
    assert values[b"x-civicos-organization-id"] == b"10000000-0000-0000-0000-000000000001"
    assert values[b"x-civicos-user-id"] == b"20000000-0000-0000-0000-000000000001"
    assert values[b"x-civicos-role"] == b"tenant_admin"
    assert values[b"authorization"] == b"Bearer verified"


def test_public_beta_feedback_validates_without_requiring_authenticated_headers() -> None:
    response = TestClient(app).post(
        "/public/beta-feedback",
        json={
            "category": "idea",
            "message": "Make source coverage more visible.",
            "page_path": "/",
        },
    )

    assert response.status_code == 503


def test_public_beta_analytics_rejects_a_path_with_query_data() -> None:
    response = TestClient(app).post(
        "/public/analytics/events",
        json={
            "event_name": "beta_page_view",
            "page_path": "/search?query=housing",
            "surface": "landing",
        },
    )

    assert response.status_code == 422


def test_cors_normalizes_pydantic_urls_to_the_browser_origin_format() -> None:
    origin = "https://civicos-frontend-two.vercel.app"
    settings = Settings.model_validate({"CIVICOS_API_CORS_ORIGINS": [origin]})
    cors_test_app = FastAPI()
    cors_test_app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origin_strings(settings),
        allow_methods=["POST"],
        allow_headers=["Content-Type"],
    )

    response = TestClient(cors_test_app).options(
        "/auth/founder/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert str(settings.cors_origins[0]) == f"{origin}/"
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
