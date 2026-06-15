"""Local connector-secret store: persistence + process-env application."""

import os

from tiles_ai.secrets import SecretStore

KEY = "TILES_TEST_SECRET_KEY"  # unique name so we never touch a real var


def test_set_persists_and_applies_to_env(tmp_path, monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    path = tmp_path / "secrets.local.yaml"
    store = SecretStore.load(path)

    store.set(KEY, "abc123")

    assert os.environ[KEY] == "abc123"  # live immediately
    assert path.exists()
    # A fresh load sees it and can re-apply to a clean env.
    monkeypatch.delenv(KEY, raising=False)
    SecretStore.load(path).apply_to_env()
    assert os.environ[KEY] == "abc123"


def test_apply_to_env_does_not_clobber_exported_var(tmp_path, monkeypatch):
    path = tmp_path / "secrets.local.yaml"
    SecretStore({KEY: "stored"}, path=path)._save()
    monkeypatch.setenv(KEY, "exported")  # user exported it explicitly

    SecretStore.load(path).apply_to_env()

    assert os.environ[KEY] == "exported"  # setdefault: export wins at startup


def test_remove_clears_value_and_env(tmp_path, monkeypatch):
    monkeypatch.delenv(KEY, raising=False)
    path = tmp_path / "secrets.local.yaml"
    store = SecretStore.load(path)
    store.set(KEY, "x")
    assert store.has(KEY)

    store.remove(KEY)

    assert not store.has(KEY)
    assert KEY not in os.environ
