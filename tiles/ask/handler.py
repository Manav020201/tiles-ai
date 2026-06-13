"""Ask — general-purpose Q&A.

The whole behavior lives in PromptTile + the manifest instructions. This is the
minimal tile: copy this folder, change the instructions, and you have a new
instant tile.
"""

from tiles_ai.handlers import PromptTile


class Ask(PromptTile):
    """Answer the user's question with the default brain."""
