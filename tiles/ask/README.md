# Ask

An **instant** tile — no connector, no credentials. Ask the model anything; it
answers with your default brain. This is the fastest proof that Tiles AI works:
connect a brain, tap Ask, type a question.

Behavior is entirely in `manifest.yaml` (`instructions`); the handler is a
one-line `PromptTile` subclass. To make your own instant tile, copy this folder
and change the instructions.
