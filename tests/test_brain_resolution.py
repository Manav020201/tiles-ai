import pytest

from tiles_ai.contracts import (
    BrainConfig,
    BrainResolutionError,
    ModelRef,
    resolve_brain,
)


def _config():
    return BrainConfig.model_validate(
        {
            "providers": [
                {
                    "id": "my-cloud",
                    "kind": "hosted",
                    "provider": "anthropic",
                    "api_key": "sk-test",
                    "model": "claude-opus-4-8",
                },
                {
                    "id": "my-local",
                    "kind": "local",
                    "endpoint": "http://localhost:11434",
                    "model": "llama3",
                },
            ],
            "default_provider": "my-cloud",
        }
    )


def test_no_model_resolves_to_default_brain():
    """Phase 1 requirement: a tile with no model uses the global default."""
    resolved = resolve_brain(None, _config())
    assert resolved.source == "default"
    assert resolved.provider == "anthropic"
    assert resolved.model == "claude-opus-4-8"
    assert resolved.provider_id == "my-cloud"
    assert resolved.badge_label == "default"


def test_no_default_configured_raises():
    config = BrainConfig.model_validate({"providers": [], "default_provider": None})
    with pytest.raises(BrainResolutionError):
        resolve_brain(None, config)


def test_pinned_model_matches_configured_provider():
    ref = ModelRef(provider="anthropic", model="claude-opus-4-8")
    resolved = resolve_brain(ref, _config())
    assert resolved.source == "pinned"
    assert resolved.provider_id == "my-cloud"  # matched -> credentials available
    assert resolved.badge_label.startswith("pinned:")


def test_pinned_local_model_matches_on_endpoint():
    ref = ModelRef(provider="local", model="llama3", endpoint="http://localhost:11434")
    resolved = resolve_brain(ref, _config())
    assert resolved.source == "pinned"
    assert resolved.provider_id == "my-local"
    assert resolved.endpoint == "http://localhost:11434"


def test_pinned_model_with_no_matching_provider_still_resolves():
    # Honest badge even when no configured provider backs it; the adapter
    # decides runnability later.
    ref = ModelRef(provider="openai", model="gpt-4o")
    resolved = resolve_brain(ref, _config())
    assert resolved.source == "pinned"
    assert resolved.provider_id is None


def test_default_provider_must_exist():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BrainConfig.model_validate({"providers": [], "default_provider": "ghost"})
