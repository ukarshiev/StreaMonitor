"""Startup override contract, without importing bots or opening sockets."""
import json
import runpy
from pathlib import Path


PARAMETERS = Path(__file__).resolve().parents[1] / "parameters.py"


def test_startup_overrides(monkeypatch, tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"SEGMENT_TIME": 120, "WANTED_RESOLUTION": 720,
                                "RESOLUTION_PREF": "exact", "MIN_FREE_DISK_PERCENT": 4.5,
                                "CONTAINER": "mkv", "WEBSERVER_PASSWORD": "ignored"}))
    monkeypatch.setenv("STRMNTR_OVERRIDES_PATH", str(path))
    monkeypatch.setenv("STRMNTR_PASSWORD", "test-only")
    values = runpy.run_path(str(PARAMETERS))
    assert values["SEGMENT_TIME"] == 120
    assert values["WANTED_RESOLUTION"] == 720
    assert values["WANTED_RESOLUTION_PREFERENCE"] == "exact"
    assert values["MIN_FREE_DISK_PERCENT"] == 4.5
    assert values["CONTAINER"] == "mkv"
    assert values["WEBSERVER_PASSWORD"] == "test-only"


def test_invalid_and_missing_overrides_keep_environment(monkeypatch, tmp_path):
    path = tmp_path / "overrides.json"
    monkeypatch.setenv("STRMNTR_OVERRIDES_PATH", str(path))
    monkeypatch.setenv("STRMNTR_RESOLUTION", "1080")
    for content in (None, "broken", "[]", '{"WANTED_RESOLUTION":true,"SEGMENT_TIME":-1,"CONTAINER":"bad"}'):
        if content is not None:
            path.write_text(content)
        values = runpy.run_path(str(PARAMETERS))
        assert values["WANTED_RESOLUTION"] == 1080
