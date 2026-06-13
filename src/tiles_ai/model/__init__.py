"""The model ("brain") layer — provider config store + model adapter.

`BrainStore` holds the user's provider config and default brain; `ModelAdapter`
resolves a tile's brain and runs completions through the right client. See
SPEC.md "The brain layer".
"""

from __future__ import annotations

from .adapter import (
    ClientFactory,
    ModelAdapter,
    TestResult,
    default_client_factory,
    echo_client_factory,
)
from .clients import (
    AnthropicClient,
    EchoModelClient,
    ModelClient,
    ModelClientError,
    OllamaClient,
)
from .store import BrainStore

__all__ = [
    "BrainStore",
    "ModelAdapter",
    "TestResult",
    "ClientFactory",
    "default_client_factory",
    "echo_client_factory",
    "ModelClient",
    "ModelClientError",
    "EchoModelClient",
    "OllamaClient",
    "AnthropicClient",
]
