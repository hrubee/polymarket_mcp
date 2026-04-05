Release a new version of Polymarket MCP.

Steps:
1. Run `python scripts/version_bump.py <version>` to update version in pyproject.toml and __init__.py
2. Update CHANGELOG.md with the new version's changes
3. Commit: `git add -A && git commit -m "release: v<version>"`
4. Push: `git push origin main`
5. The auto-tag workflow will create a git tag automatically
