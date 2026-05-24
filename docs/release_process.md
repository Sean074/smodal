# Release process

This document codifies how a new version of `smodal` is released. It is short on purpose — one developer, one branch model, one ritual.

---

## 1. Versioning

`smodal` follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

| Change | Bump | Example |
|---|---|---|
| Bug fix only, no behaviour change for users | `PATCH` | `1.0.0` → `1.0.1` |
| New feature, backward-compatible | `MINOR` | `1.0.0` → `1.1.0` |
| Breaking change (input format, public API, removed page, etc.) | `MAJOR` | `1.0.0` → `2.0.0` |

The version lives in **one place only**: the `version = "..."` field in [`pyproject.toml`](../pyproject.toml). Everywhere else reads it via `importlib.metadata.version("smodal")` if needed.

---

## 2. Branch model

| Branch | Purpose | Lifetime |
|---|---|---|
| `main` | Always releasable. Every commit on `main` corresponds to (or is on the path to) a tagged release. | Permanent |
| `feature/<name>` | New functionality. Example: `feature/viewer-rewrite`. | Until merged |
| `fix/issue-<n>` | Bug fixes tied to a GitHub issue. Example: `fix/issue-42`. | Until merged |

Workflow:

```bash
git checkout main
git pull
git checkout -b feature/<name>     # or fix/issue-<n>
# … work, commit …
git push -u origin feature/<name>
# Open a PR (or merge locally) when ready
```

Merge back to `main` with `--no-ff` so the branch shows up as a merge commit in `git log`:

```bash
git checkout main
git merge --no-ff feature/<name>
git branch -d feature/<name>
git push origin --delete feature/<name>     # or rely on GitHub auto-delete
```

---

## 3. Pre-release checklist

Run through this list **before** tagging. If any item fails, fix it on a branch and merge first.

- [ ] All critical and major issues in `todo.md` are resolved.
- [ ] `pytest tests/ -v` passes locally.
- [ ] `ruff check .` returns no errors.
- [ ] Manual smoke run: `streamlit run app.py` → walk through pages 1 → 9 with `data/input/sample_3ch.csv` → no exceptions, no rendering glitches.
- [ ] `pip install -e .` succeeds in a clean virtual environment.
- [ ] `requirements.txt` and `pyproject.toml` dependency lists agree.
- [ ] [`CHANGELOG.md`](../CHANGELOG.md) has an entry for the new version under a real header (not `[Unreleased]`), with today's date.
- [ ] [`pyproject.toml`](../pyproject.toml) `version` field matches the changelog header.
- [ ] No accidentally-committed analysis outputs in `data/output/` or stray notebooks with embedded data.

---

## 4. Release procedure

Once the checklist passes:

```bash
# 1. Final commit on the release branch (or main)
git add CHANGELOG.md pyproject.toml
git commit -m "Release vX.Y.Z"

# 2. Merge into main (skip if already on main)
git checkout main
git merge --no-ff <release-branch>
git push origin main

# 3. Create an ANNOTATED tag — not lightweight
git tag -a vX.Y.Z -m "Release vX.Y.Z — <one-line summary>"
git push origin vX.Y.Z

# 4. Publish a GitHub Release
#    GitHub → Releases → Draft a new release
#      • Tag: vX.Y.Z (already pushed)
#      • Title: vX.Y.Z — <one-line summary>
#      • Body: paste the CHANGELOG.md entry for this version
#      • Publish
```

Annotated tags (`-a`) are required because they carry a message, are searchable, and can be signed later if needed.

---

## 5. After release

- Create a new `[Unreleased]` section at the top of `CHANGELOG.md` for the next round of work.
- Bump `pyproject.toml` to the next anticipated dev version if you prefer to work against `X.Y.(Z+1)-dev` (optional; many solo projects don't bother).
- Close any GitHub issues that the release resolved.
- Tell anyone who depends on the project that there's a new release (if applicable).

---

## 6. Hotfix procedure

For an urgent fix against an already-released version:

```bash
git checkout vX.Y.Z          # the tag
git checkout -b fix/issue-<n>
# … fix …
git checkout main
git merge --no-ff fix/issue-<n>
# Bump PATCH version in pyproject.toml, update CHANGELOG.md
git commit -am "Release vX.Y.(Z+1)"
git tag -a vX.Y.(Z+1) -m "Hotfix: <issue summary>"
git push origin main vX.Y.(Z+1)
```

---

## 7. What is *not* in this process (deliberately)

- **No branch protection rules on `main`.** Solo developer; blocking yourself is friction without benefit. Revisit if/when a second contributor joins.
- **No required code review.** Self-review at merge time is sufficient.
- **No pre-commit hooks.** `ruff` and `pytest` run in CI on push — that is the safety net.
- **No release candidates (`-rc1`) below MAJOR releases.** Use the `[Unreleased]` section of the changelog as your "in-flight" staging area.

If the project grows past one developer or starts being depended on by other software, revisit each of these.
