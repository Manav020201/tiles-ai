# Releasing

Releases are built and published to PyPI by CI on a version tag.

## One-time setup

1. On PyPI, configure **Trusted Publishing** for the `tiles-ai` project pointing
   at this GitHub repo and the `release.yml` workflow (no API token needed).
2. Create a GitHub Environment named `pypi` (Settings → Environments).

## Pre-flight checklist

- [ ] `pyproject.toml` `[project.urls]` and the README CI badge point at the real repo
- [ ] `authors` in `pyproject.toml` is correct
- [ ] The PyPI project name (`tiles-ai`) is available / owned by you
- [ ] PyPI Trusted Publishing + the `pypi` environment are configured (above)
- [ ] CI is green on `main`
- [ ] `CHANGELOG.md` has an entry for the new version

## Cut a release

1. Bump the version in `pyproject.toml` and `src/tiles_ai/__init__.py`.
2. Move the `CHANGELOG.md` `[Unreleased]` items under the new version + date.
3. Commit, then tag and push:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

The [release workflow](.github/workflows/release.yml) then:

- builds the React board (`frontend/`) and copies `frontend/dist` into
  `src/tiles_ai/web/` so the board ships **inside the wheel** (this dir is
  gitignored — it only exists during the release build),
- bundles the **starter board** (`connectors/`, `tiles/`, `examples/`,
  `sample_docs/`) into `src/tiles_ai/starter_board/` via
  `scripts/bundle_starter.py`, so `tiles init` / `tiles up` can seed it for users
  who installed from PyPI (also gitignored, generated at build time),
- builds the sdist + wheel,
- publishes to PyPI via Trusted Publishing.

After release, `pipx install tiles-ai && tiles up` seeds a starter board into the
current folder, then serves the API and the bundled board on one port.

## Verify a build locally

```bash
npm --prefix frontend run build
cp -r frontend/dist src/tiles_ai/web
python scripts/bundle_starter.py    # -> src/tiles_ai/starter_board/
python -m build                     # produces dist/*.whl with both bundled
rm -rf src/tiles_ai/web src/tiles_ai/starter_board
```
