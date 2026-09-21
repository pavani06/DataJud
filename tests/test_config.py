from pathlib import Path

import pytest

from app.config import Settings


def test_defaults_work_without_a_key(monkeypatch):
    for key in ("API_KEY", "TIMEOUT_SECONDS", "DATA_DIR", "MAX_RETRIES"):
        monkeypatch.delenv(f"DATAJUD_{key}", raising=False)
    settings = Settings.from_env()
    assert settings.api_key == ""
    assert settings.timeout_seconds == 30
    assert settings.max_retries == 2
    assert settings.data_dir == Path("data")


def test_environment_and_safe_repr(monkeypatch, tmp_path):
    monkeypatch.setenv("DATAJUD_API_KEY", "  test-only-key  ")
    monkeypatch.setenv("DATAJUD_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("DATAJUD_MAX_RETRIES", "1")
    monkeypatch.setenv("DATAJUD_DATA_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert settings.api_key == "test-only-key"
    assert settings.timeout_seconds == 2.5
    assert settings.max_retries == 1
    assert settings.data_dir == tmp_path
    assert "test-only-key" not in repr(settings)


@pytest.mark.parametrize("kwargs", [
    {"timeout_seconds": 0}, {"timeout_seconds": -1}, {"timeout_seconds": True},
    {"timeout_seconds": float("nan")}, {"timeout_seconds": float("inf")},
    {"max_retries": -1}, {"max_retries": 4}, {"max_retries": True},
    {"api_key": "test-only\r\nInjected: value"}, {"api_key": "non-ascii-é"},
    {"api_key": None}, {"data_dir": ""}, {"data_dir": "\x00"},
])
def test_invalid_configuration_is_rejected_without_echoing_values(kwargs):
    with pytest.raises(ValueError) as caught:
        Settings(**kwargs)
    assert "test-only" not in str(caught.value)
    assert "non-ascii" not in str(caught.value)


@pytest.mark.parametrize("name,value", [
    ("DATAJUD_TIMEOUT_SECONDS", "not-a-number"),
    ("DATAJUD_TIMEOUT_SECONDS", "NaN"),
    ("DATAJUD_MAX_RETRIES", "1.5"),
    ("DATAJUD_MAX_RETRIES", "4"),
])
def test_bad_environment_is_explicit(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()
