"""Extract — structured info from free text. Behavior is in the manifest."""

from tiles_ai.handlers import PromptTile


class Extract(PromptTile):
    """Extract entities and action items with the default brain."""
