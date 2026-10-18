from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from kokoro_app.app import create_app


def client_for(path: Path) -> TestClient:
    return TestClient(create_app(preload_model=False, fish_voice_db=path))


def test_voice_library_crud_persists_across_app_instances(tmp_path: Path) -> None:
    path = tmp_path / "voices.sqlite3"
    client = client_for(path)
    initial = client.get("/api/fish-voices").json()
    assert initial[0]["reference_id"] == "b0204e37cbc94a16954c78697b844af2"

    response = client.post("/api/fish-voices", json={"name": " Narrator ", "reference_id": " voice-one "})
    assert response.status_code == 201
    saved = response.json()
    assert saved == {"id": saved["id"], "name": "Narrator", "description": "", "reference_id": "voice-one"}
    assert saved in client_for(path).get("/api/fish-voices").json()

    updated = client.put(f"/api/fish-voices/{saved['id']}", json={"name": "Updated", "reference_id": "voice-two"})
    assert updated.status_code == 200
    assert updated.json() == {"id": saved["id"], "name": "Updated", "description": "", "reference_id": "voice-two"}
    assert updated.json() in client_for(path).get("/api/fish-voices").json()

    for voice in client.get("/api/fish-voices").json():
        assert client.delete(f"/api/fish-voices/{voice['id']}").status_code == 200
    # Empty libraries stay empty: deleting the starter reference is permanent.
    assert client_for(path).get("/api/fish-voices").json() == []


@pytest.mark.parametrize("payload", [
    {"name": " ", "reference_id": "voice-one"},
    {"name": "Narrator", "reference_id": " "},
    {"name": "x" * 101, "reference_id": "voice-one"},
    {"name": "Narrator", "reference_id": "x" * 257},
    {},
])
def test_invalid_voice_references_are_actionable(tmp_path: Path, payload: dict) -> None:
    response = client_for(tmp_path / "voices.sqlite3").post("/api/fish-voices", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_voice_reference"


def test_duplicates_and_missing_references_do_not_overwrite_saved_voices(tmp_path: Path) -> None:
    client = client_for(tmp_path / "voices.sqlite3")
    first = client.post("/api/fish-voices", json={"name": "One", "reference_id": "one"}).json()
    second = client.post("/api/fish-voices", json={"name": "Two", "reference_id": "two"}).json()
    assert client.post("/api/fish-voices", json={"name": "Other", "reference_id": " one "}).status_code == 409
    assert client.put(f"/api/fish-voices/{second['id']}", json={"name": "Other", "reference_id": "one"}).status_code == 409
    assert first in client.get("/api/fish-voices").json()
    assert second in client.get("/api/fish-voices").json()
    assert client.put("/api/fish-voices/missing", json={"name": "Missing", "reference_id": "three"}).status_code == 404
    assert client.delete("/api/fish-voices/missing").status_code == 404


def test_unavailable_storage_reports_an_error_instead_of_an_empty_library(tmp_path: Path) -> None:
    path = tmp_path / "voices.sqlite3"
    path.mkdir()
    response = client_for(path).get("/api/fish-voices")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "voice_library_unavailable"


def test_description_and_voice_url_are_normalized_and_persisted(tmp_path: Path) -> None:
    path = tmp_path / "voices.sqlite3"
    client = client_for(path)
    created = client.post("/api/fish-voices", json={
        "name": "FairyTail", "description": " Storytelling, narrating ",
        "reference_id": "https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/?share=1#voice",
    })
    assert created.status_code == 201
    saved = created.json()
    assert saved["reference_id"] == "689b47ca83dd48dba90b160affb8a118"
    assert saved["description"] == "Storytelling, narrating"
    assert saved in client_for(path).get("/api/fish-voices").json()
    assert client.post("/api/fish-voices", json={"name": "Duplicate", "reference_id": saved["reference_id"]}).status_code == 409
    edited = client.put(f"/api/fish-voices/{saved['id']}", json={
        "name": "FairyTail", "description": "Warm stories", "reference_id": saved["reference_id"],
    }).json()
    assert edited["description"] == "Warm stories"


@pytest.mark.parametrize("reference", [
    "https://example.com/app/m/689b47ca83dd48dba90b160affb8a118/",
    "https://fish.audio/app/discovery/", "https://fish.audio/app/m/missing/",
    "https://fish.audio.evil.com/app/m/689b47ca83dd48dba90b160affb8a118/",
])
def test_invalid_voice_urls_are_rejected(tmp_path: Path, reference: str) -> None:
    response = client_for(tmp_path / "voices.sqlite3").post("/api/fish-voices", json={"name": "Voice", "reference_id": reference})
    assert response.status_code == 422
    assert "Fish Audio voice URL" in response.json()["error"]["message"]


def test_existing_library_is_migrated_without_changing_voices(tmp_path: Path) -> None:
    path = tmp_path / "voices.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE fish_voices (id TEXT PRIMARY KEY, name TEXT NOT NULL, reference_id TEXT NOT NULL UNIQUE)")
        connection.execute("INSERT INTO fish_voices VALUES ('old', 'Existing voice', 'existing-ref')")
    client = client_for(path)
    assert client.get("/api/fish-voices").json() == [{"id": "old", "name": "Existing voice", "reference_id": "existing-ref", "description": ""}]
    response = client.put("/api/fish-voices/old", json={"name": "Existing voice", "reference_id": "existing-ref", "description": "Now with notes"})
    assert response.status_code == 200
    assert response.json()["description"] == "Now with notes"


def test_paginated_voices_have_stable_order_and_total(tmp_path: Path) -> None:
    client = client_for(tmp_path / "voices.sqlite3")
    for i in reversed(range(12)):
        client.post("/api/fish-voices", json={"name": f"Voice {i:02}", "reference_id": f"voice-{i}", "description": f"Notes {i}"})
    first = client.get("/api/fish-voices/page?page=1&page_size=10").json()
    second = client.get("/api/fish-voices/page?page=2&page_size=10").json()
    assert first["total"] == second["total"] == 13
    assert len(first["items"]) == 10
    assert [item["name"] for item in second["items"]] == ["Voice 09", "Voice 10", "Voice 11"]
    assert set(item["id"] for item in first["items"]).isdisjoint(item["id"] for item in second["items"])
    assert client.get("/api/fish-voices/page?page=0").status_code == 422
    assert client.get("/api/fish-voices/page?page_size=1000").status_code == 422


def test_legacy_references_remain_manageable_and_case_variants_cannot_be_duplicated(tmp_path: Path) -> None:
    path = tmp_path / "voices.sqlite3"
    upper = "689B47CA83DD48DBA90B160AFFB8A118"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE fish_voices (id TEXT PRIMARY KEY, name TEXT NOT NULL, reference_id TEXT NOT NULL UNIQUE)")
        connection.executemany("INSERT INTO fish_voices VALUES (?, ?, ?)", [
            ("old", "Existing voice", upper),
            ("invalid", "Previously accepted URL", "https://example.com/voice"),
        ])
    client = client_for(path)
    response = client.get("/api/fish-voices")
    assert response.status_code == 200
    assert response.json()[0]["reference_id"] == upper
    assert client.get("/api/fish-voices/page").status_code == 200
    assert client.post("/api/fish-voices", json={"name": "Duplicate", "reference_id": upper.lower()}).status_code == 409
    assert client.put("/api/fish-voices/invalid", json={"name": "Duplicate", "reference_id": upper.lower()}).status_code == 409
    assert client.delete("/api/fish-voices/invalid").status_code == 200
    edited = client.put("/api/fish-voices/old", json={"name": "Updated", "description": "Notes", "reference_id": upper})
    assert edited.status_code == 200
    assert edited.json()["reference_id"] == upper.lower()
