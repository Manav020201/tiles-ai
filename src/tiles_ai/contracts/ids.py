"""Shared identifier conventions.

Connector ids, tile ids, and provider ids are all lowercase kebab/snake slugs.
Keeping the pattern in one place means a manifest, the registry, and the brain
store all agree on what a legal id looks like.
"""

from __future__ import annotations

# Lowercase alphanumerics, separated by single hyphens or underscores.
# Examples: 'gmail', 'gmail-draft', 'my_local_ollama'.
SLUG_PATTERN = r"^[a-z0-9]+([_-][a-z0-9]+)*$"
