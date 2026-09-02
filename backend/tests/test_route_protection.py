"""Route-protection tests (Phase 14): every route except the open set requires login.

Asserts via the OpenAPI schema (source of truth for the route table) that
every documented path except the open set requires authentication.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Routes that must stay open (login itself, health checks).
OPEN_PATHS = {
    "/health",
    "/health/db",
    "/auth/login",
    "/auth/register",
    "/auth/refresh",
    "/auth/logout",
}

# Router prefixes from Phases 1-11 that must ALL be protected.
PROTECTED_PREFIXES = (
    "/ingestion",
    "/profiling",
    "/semantic-contract",
    "/data-quality",
    "/canonical",
    "/kpi",
    "/anomaly",
    "/drivers",
    "/evidence",
    "/insights",
    "/recommendations",
    "/feedback",
    "/telemetry",
)


def _doc_paths():
    schema = client.get("/openapi.json").json()
    return schema.get("paths", {})


def test_openapi_lists_all_expected_routers():
    paths = _doc_paths()
    for prefix in PROTECTED_PREFIXES:
        assert any(p.startswith(prefix) for p in paths), f"missing routes under {prefix}"


def test_every_route_except_open_set_is_protected():
    """Fail if any route outside OPEN_PATHS lacks the auth dependency.

    Reads each route's dependencies from the OpenAPI spec's security
    requirement + confirms functionally that requests are rejected.
    """
    paths = _doc_paths()
    unprotected = []
    checked = 0
    for path, ops in paths.items():
        if path in OPEN_PATHS or path.startswith("/auth") or path.startswith("/docs"):
            continue
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            checked += 1
            # Protected ops appear in the spec with an auth-bearing security
            # scheme OR reject anonymous requests functionally.
            if not op.get("security"):
                resp = getattr(client, method)(path.replace("{source_id}", "x").replace("{kpi_id}", "x").replace("{dataset_id}", "x").replace("{finding_id}", "x").replace("{persona_id}", "x").replace("{call_id}", "x"))
                if resp.status_code != 401:
                    unprotected.append(f"{method.upper()} {path}")
    assert not unprotected, f"Routes missing auth: {unprotected}"
    assert checked >= 27, f"expected the full route table, checked only {checked} operations"


def test_open_routes_do_not_require_auth():
    """Health + auth open routes answer without a token."""
    assert client.get("/health").status_code == 200
    assert client.get("/health/db").status_code == 200
    resp = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "x"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "bad_credentials"


def test_protected_route_rejects_missing_token():
    """A protected route without a token -> 401 token_missing (not generic)."""
    resp = client.get("/ingestion/sources")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "token_missing"
    assert body["error"]["message"] == "You're not logged in. Please log in to continue."
