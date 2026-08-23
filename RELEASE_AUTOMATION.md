# Release Automation

The current GitHub workflow is `.github/workflows/release-please.yml`, but the
job is a custom **version-tag** release job. It computes the next tag from repo
variables or manual workflow inputs.

## What happens automatically

1. A push to `main` runs `.github/workflows/release-please.yml`.
2. The workflow reads `MASTER_BUILD_NUMBER` and `IS_RELEASE`.
3. It finds the next revision for that major/minor line.
4. It creates a git tag:
   - stable: `vX.Y.Z`
   - alpha: `vX.Y.Z-alpha`
5. It creates a GitHub Release for that tag.

## Required repo variables

- `MASTER_BUILD_NUMBER`: base version like `1.0` or `1.0.X`
- `IS_RELEASE`: `true` for stable tags, `false` for alpha tags

The workflow can also be run manually with `workflow_dispatch` inputs.

## Production device updates

After a tag is created, update a Pi with:

```bash
cd /home/zaid/metroclock
./scripts/update_pi.sh --ref v1.0.3-alpha
```

See `PRODUCTION_UPDATES.md` for the full device update and rollback flow.
