"""End-to-end tests for PocketSmart AI (run with:  pytest -v)."""
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.services import catalog, gemini_utils
from main import app

PASSWORD = "Sup3rSecret!"


@pytest.fixture
def client():
    with TestClient(app) as c:  # `with` runs the startup (DB creation)
        yield c


def _register_and_login(c: TestClient) -> str:
    name = "user_" + uuid.uuid4().hex[:8]
    r = c.post("/register", data={"username": name, "email": f"{name}@example.com",
                                  "password": PASSWORD, "confirm_password": PASSWORD},
               follow_redirects=False)
    assert r.status_code == 303 and "/login" in r.headers["location"]
    r = c.post("/login", data={"username": name, "password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/dashboard"
    return name


@pytest.fixture
def auth(client):
    client.username = _register_and_login(client)
    return client


HOME = {"budget": 150000, "style": "Modern",
        "rooms": [{"room_type": "Living Room", "items": [{"name": "Lights", "quantity": 4}, {"name": "Sofa", "quantity": 1}]},
                  {"room_type": "Kitchen", "items": [{"name": "Ceiling fans", "quantity": 1}]}]}
PARTY = {"budget": 60000, "guests": 40, "event_type": "Birthday", "venue": "Home terrace", "city": "Coimbatore"}


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (180, 30, 60)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- public pages / auth
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "PocketSmart" in r.text and "Testimonials" in r.text


def test_static_css(client):
    assert client.get("/static/css/styles.css").status_code == 200


def test_unknown_page_404(client):
    assert client.get("/nope", headers={"accept": "text/html"}).status_code == 404


@pytest.mark.parametrize("path", ["/dashboard", "/home-planner", "/party-planner",
                                  "/jewelry-planner", "/history", "/recommendations/1"])
def test_pages_redirect_when_logged_out(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_api_requires_login(client):
    assert client.post("/generate-home", json=HOME).status_code == 401
    assert client.get("/session-data").status_code == 401
    assert client.get("/session-info").json() == {"logged_in": False}


def test_register_validation_and_duplicates(client):
    bad = client.post("/register", data={"username": "ab", "email": "x", "password": "1", "confirm_password": "2"})
    assert bad.status_code == 400
    name = "dup_" + uuid.uuid4().hex[:6]
    data = {"username": name, "email": f"{name}@example.com", "password": PASSWORD, "confirm_password": PASSWORD}
    assert client.post("/register", data=data, follow_redirects=False).status_code == 303
    assert client.post("/register", data=data).status_code == 400  # duplicate


def test_login_wrong_password(client):
    r = client.post("/login", data={"username": "ghost", "password": "wrongpass1"})
    assert r.status_code == 401 and "Incorrect" in r.text


def test_login_session_logout(auth):
    info = auth.get("/session-info").json()
    assert info["logged_in"] and info["username"] == auth.username
    assert auth.get("/dashboard").status_code == 200
    auth.get("/logout", follow_redirects=False)
    assert auth.get("/dashboard", follow_redirects=False).status_code == 303


def test_token_endpoint_and_bearer_auth(client):
    name = _register_and_login(client)
    client.cookies.clear()
    r = client.post("/token", data={"username": name, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    token = r.json()["access_token"]
    ok = client.get("/session-data", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200 and ok.json()["username"] == name
    assert client.post("/token", data={"username": name, "password": "bad"}).status_code == 401


# ---------------------------------------------------------------- planners
def test_home_planner_flow(auth):
    assert auth.get("/home-planner").status_code == 200
    r = auth.post("/generate-home", json=HOME)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "fallback" and body["redirect"] == f"/recommendations/{body['id']}"
    res = body["result"]
    assert {s["title"] for s in res["sections"]} == {"Living Room", "Kitchen"}
    assert res["estimated_total"] <= HOME["budget"]
    assert all(i["url"].startswith("https://") for s in res["sections"] for i in s["items"])
    page = auth.get(body["redirect"])
    assert page.status_code == 200 and "Living Room" in page.text and "₹" in page.text


def test_party_planner_flow(auth):
    assert auth.get("/party-planner").status_code == 200
    r = auth.post("/generate-party", json=PARTY)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    titles = [s["title"] for s in res["sections"]]
    assert "Catering" in titles and "Decoration" in titles
    assert res["estimated_total"] <= PARTY["budget"]
    assert auth.get(r.json()["redirect"]).status_code == 200


def test_jewelry_planner_with_image(auth):
    assert auth.get("/jewelry-planner").status_code == 200
    r = auth.post("/generate-jewelry",
                  data={"budget": "25000", "occasion": "Wedding", "style": "Traditional", "metal": "Gold"},
                  files={"outfit_image": ("outfit.png", _png_bytes(), "image/png")})
    assert r.status_code == 200, r.text
    page = auth.get(r.json()["redirect"])
    assert page.status_code == 200 and "/static/uploads/" in page.text


def test_jewelry_planner_without_image(auth):
    r = auth.post("/generate-jewelry", data={"budget": "8000", "occasion": "Festival"})
    assert r.status_code == 200 and r.json()["result"]["sections"]


def test_jewelry_rejects_non_image(auth):
    r = auth.post("/generate-jewelry", data={"budget": "8000", "occasion": "Party"},
                  files={"outfit_image": ("evil.png", b"not really an image", "image/png")})
    assert r.status_code == 400


@pytest.mark.parametrize("payload", [
    {**HOME, "budget": -5}, {**HOME, "rooms": []},
    {**HOME, "rooms": [{"room_type": "Kitchen", "items": [{"name": "Lights", "quantity": 0}]}]},
])
def test_home_validation(auth, payload):
    assert auth.post("/generate-home", json=payload).status_code == 422


def test_party_validation(auth):
    assert auth.post("/generate-party", json={**PARTY, "guests": 0}).status_code == 422
    assert auth.post("/generate-party", json={**PARTY, "budget": 0}).status_code == 422


# ---------------------------------------------------------------- history / details / isolation
def test_history_details_delete_and_isolation(auth):
    rec_id = auth.post("/generate-party", json=PARTY).json()["id"]
    assert "Birthday" in auth.get("/history").text
    assert auth.get("/history?category=home").status_code == 200
    assert any(r["id"] == rec_id for r in auth.get("/api/history").json())
    assert auth.get(f"/recommendations-details?id={rec_id}").json()["category"] == "party"
    assert auth.get("/recommendations-details?category=bogus").status_code == 400
    assert auth.get("/session-data").json()["counts_by_category"]["party"] >= 1

    with TestClient(app) as other:  # another user must not see it
        _register_and_login(other)
        assert other.get(f"/recommendations/{rec_id}", headers={"accept": "text/html"}).status_code == 404
        assert other.get(f"/recommendations-details?id={rec_id}").status_code == 404

    assert auth.post(f"/history/{rec_id}/delete", follow_redirects=False).status_code == 303
    assert auth.get(f"/recommendations-details?id={rec_id}").status_code == 404


# ---------------------------------------------------------------- Gemini layer (mocked)
def test_gemini_success_path(auth, monkeypatch):
    fake = ('```json\n{"summary":"ok","sections":[{"title":"Catering","allocated_budget":"₹30,000",'
            '"items":[{"name":"Biryani box","platform":"zomato","quantity":40,"estimated_price":"₹500",'
            '"why":"popular","url":"http://evil.example"}]}],"tips":["Order early"]}\n```')
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(gemini_utils, "call_gemini", lambda prompt, image=None: fake)
    body = auth.post("/generate-party", json=PARTY).json()
    assert body["source"] == "gemini"
    item = body["result"]["sections"][0]["items"][0]
    assert item["platform"] == "Zomato" and item["total"] == 20000
    assert item["url"].startswith("https://www.zomato.com/")  # LLM URL is ignored


def test_gemini_failure_falls_back(auth, monkeypatch):
    def boom(prompt, image=None):
        raise RuntimeError("API down")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(gemini_utils, "call_gemini", boom)
    body = auth.post("/generate-home", json=HOME).json()
    assert body["source"] == "fallback" and body["result"]["sections"]


def test_gemini_garbage_falls_back(auth, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(gemini_utils, "call_gemini", lambda p, i=None: "sorry, I can't do that")
    assert auth.post("/generate-party", json=PARTY).json()["source"] == "fallback"


# ---------------------------------------------------------------- pure unit tests
def test_extract_json_variants():
    assert gemini_utils.extract_json('{"a": 1}') == {"a": 1}
    assert gemini_utils.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert gemini_utils.extract_json('Here you go: {"a": 1} hope it helps') == {"a": 1}
    with pytest.raises(ValueError):
        gemini_utils.extract_json("no json here")


def test_normalize_flags_over_budget():
    raw = {"sections": [{"title": "X", "items": [{"name": "Thing", "platform": "IKEA", "quantity": 2, "estimated_price": 6000}]}]}
    res = gemini_utils.normalize_result(raw, 10000)
    assert res["estimated_total"] == 12000 and res["over_budget"] and res["tips"]


def test_catalog_links_and_platforms():
    assert catalog.canonical_platform("amazon.in") == "Amazon"
    assert catalog.canonical_platform("something else") == "Amazon"
    assert "q=wall+art" in catalog.search_url("Flipkart", "wall art")
