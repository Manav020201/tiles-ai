# Releasing

Releases are built and published to PyPI by CI on a version tag.

## One-time setup

1. On PyPI, configure **Trusted Publishing** for the `tiles-ai` project pointing
   at this GitHub repo and the `release.yml` workflow (no API token needed).
2. Create a GitHub Environment named `pypi` (Settings → Environments).

## Cut a release

1. Bump the version in `pyproject.toml` and `src/tiles_ai/__init__.py`.
2. Update `CHANGELOG.md`.
3. Commit, then tag and push:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

The [release workflow](.github/workflows/release.yml) then:

- builds the React board (`frontend/`) and copies `frontend/dist` into
  `src/tiles_ai/web/` so the board ships **inside the wheel** (this dir is
  gitignored — it only exists during the release build),
- builds the sdist + wheel,
- publishes to PyPI via Trusted Publishing.

After release, `pipx install tiles-ai && tiles up` serves the API and the bundled
board on one port.

## Verify a build locally

```bash
npm --prefix frontend run build
cp -r frontend/dist src/tiles_ai/web
python -m build         # produces dist/*.whl with the board bundled
rm -rf src/tiles_ai/web
```
