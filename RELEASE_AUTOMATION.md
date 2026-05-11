# Release Automation

This repo uses **release-please** with **Conventional Commits**.

## What happens automatically

1. A push to `main` runs `.github/workflows/release-please.yml`.
2. release-please scans commits since the last release tag.
3. It opens or updates a **Release PR** with:
   - `CHANGELOG.md` updates
   - `version.txt` bump
   - `.release-please-manifest.json` version bump
4. When that Release PR is merged, release-please creates:
   - a git tag (`vX.Y.Z`)
   - a GitHub Release

## Commit format to use

- `feat: ...` -> minor bump
- `fix: ...` -> patch bump
- `feat!: ...` or `BREAKING CHANGE:` in body -> major bump

Examples:

- `feat: add iOS device pairing endpoint`
- `fix: persist ambient scene across restart`
- `feat!: change auth header format`

## First-time bootstrap notes

- Current manifest baseline is set in `.release-please-manifest.json`.
- If you need to force the next version manually, use an empty commit:

```bash
git commit --allow-empty -m "chore: release 0.2.0" -m "Release-As: 0.2.0"
git push origin main
```

