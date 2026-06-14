# Tidy Folder

A **draft**-tier tile over the [local-files connector](../../connectors/local-files)
— and the first tile that proposes *local* side effects. Give it a folder; it
proposes moving each file into a subfolder named by its type (e.g. `pdf/`,
`png/`). Every move queues for your approval — nothing moves until you approve it.

Point the connector at the folder you want to tidy (e.g. Downloads) by editing
`connectors/local-files/manifest.yaml`.
