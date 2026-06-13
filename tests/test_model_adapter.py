import asyncio

from tiles_ai.contracts import HostedProvider, LocalProvider, ModelRef
from tiles_ai.model import (
    BrainStore,
    EchoModelClient,
    ModelAdapter,
    echo_client_factory,
)


def _store():
    store = BrainStore()
    store.add_provider(
        HostedProvider(
            id="cloud", provider="anthropic", api_key="sk-test", model="claude-opus-4-8"
        ),
        make_default=True,
    )
    store.add_provider(
        LocalProvider(id="local", endpoint="http://localhost:11434", model="llama3")
    )
    return store


def test_first_provider_becomes_default():
    store = BrainStore()
    store.add_provider(
        HostedProvider(id="a", provider="anthropic", api_key="k", model="m")
    )
    assert store.config.default_provider == "a"


def test_resolve_default_and_complete_offline():
    adapter = ModelAdapter(_store(), client_factory=echo_client_factory)
    resolved = adapter.resolve(None)  # no pin -> default brain
    assert resolved.source == "default"
    out = asyncio.run(adapter.complete(resolved, "Hello there"))
    assert out == "[echo:claude-opus-4-8] Hello there"


def test_resolve_pinned_local():
    adapter = ModelAdapter(_store(), client_factory=echo_client_factory)
    resolved = adapter.resolve(
        ModelRef(provider="local", model="llama3", endpoint="http://localhost:11434")
    )
    assert resolved.source == "pinned"
    assert resolved.provider_id == "local"


def test_test_action_ok_offline():
    adapter = ModelAdapter(_store(), client_factory=echo_client_factory)
    result = asyncio.run(adapter.test("cloud"))
    assert result.ok
    assert "[echo:" in result.detail


def test_test_action_unknown_provider():
    adapter = ModelAdapter(_store(), client_factory=echo_client_factory)
    result = asyncio.run(adapter.test("ghost"))
    assert not result.ok


def test_default_factory_builds_real_clients_without_network():
    # Construction only — no .complete() call, so no network is touched.
    from tiles_ai.model.adapter import default_client_factory
    from tiles_ai.model import AnthropicClient, OllamaClient

    adapter = ModelAdapter(_store())  # default (real) factory
    cloud = adapter.client_for(adapter.resolve(None))
    assert isinstance(cloud, AnthropicClient)
    local = adapter.client_for(
        adapter.resolve(ModelRef(provider="local", model="llama3", endpoint="http://localhost:11434"))
    )
    assert isinstance(local, OllamaClient)


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "brain.local.yaml"
    _store().save(path)
    reloaded = BrainStore.load(path)
    assert reloaded.config.default_provider == "cloud"
    assert {p.id for p in reloaded.config.providers} == {"cloud", "local"}
