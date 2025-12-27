import os
import json
import pytest

from app import create_app
from app.utils.text import extract_concept


@pytest.fixture()
def client():
    app = create_app()
    app.config.update({"TESTING": True})
    return app.test_client()


def test_extract_concept_basic():
    assert extract_concept("Explain how a hash table works") == "hash"
    assert extract_concept("What is time complexity?") == "time"


def test_get_question(client):
    res = client.post("/get-question", json={"category": "technical"})
    assert res.status_code == 200
    data = res.get_json()
    assert "question" in data


def test_submit_answer_requires_body(client):
    res = client.post("/submit-answer", json={})
    assert res.status_code == 400


def test_dashboard_renders_empty(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
