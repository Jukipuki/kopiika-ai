# Versioning Policy

Kopiika AI uses [semantic versioning](https://semver.org) with project-specific rules for what each digit means. The canonical version lives in a single [`/VERSION`](../VERSION) file at the repo root; both backend and frontend read it at runtime/build time so they stay in sync.

## Scheme

| Digit | Bump when |
|-------|-----------|
| **MAJOR** | A phase boundary is crossed (Phase 1 → Phase 2 = `1.x.x` → `2.0.0`). |
| **MINOR** | Any story is merged — any epic, any time. |
| **PATCH** | A bug-fix or polish-only story is merged (no new user-facing functionality). |

### Invariants

- **Versions are monotonic.** They only ever increase.
- **Version digits are NOT mapped to epic numbers.** `1.5.0` does not mean "epic 5" — it means the fifth minor bump since `1.0.0`. The version number encodes progress through the product, not through our planning structure.
- **Baseline:** `1.1.0` reflects the state of the project after Story 1.8 merged. Story 1.9 (which established this policy) bumped the version to `1.2.0`.

## How to bump

The version bump happens in the **same PR** that closes a story.

1. Open [`/VERSION`](../VERSION) in your editor.
2. Increment the appropriate digit per the scheme above (MAJOR/MINOR/PATCH).
3. Commit the change as part of the story PR.

There is no automation yet — the bump is a one-line manual edit. That's intentional: automation is cheap to add later when the workflow stabilizes, and keeping it manual avoids yet another CI dependency while the team is small.

### Examples

| Situation | Current | New |
|-----------|---------|-----|
| Merging a normal feature story (e.g., Story 2.8 adds upload summary UI) | `1.2.0` | `1.3.0` |
| Merging a bug-fix story (e.g., Story 5.6 patches consent bug) | `1.3.0` | `1.3.1` |
| Starting Phase 2 of the product | `1.8.0` | `2.0.0` |

## Where the version shows up

- **Runtime (backend):** `GET /health` returns the `version` field read from [`/VERSION`](../VERSION) at process start.
- **Runtime (frontend):** `<AppVersionBadge />` renders `v{VERSION}` in a muted badge in the authenticated dashboard chrome (hidden on public and onboarding routes).
- **Source:** [`/VERSION`](../VERSION) is the single source of truth. Do not add version strings elsewhere in code — read them from this file.

## Deferred (tracked in [tech-debt.md](tech-debt.md))

This story intentionally keeps scope small. The following are out of scope and will be picked up in follow-up stories:

- `CHANGELOG.md` / release notes
- Bump automation (scripts, make targets, pre-commit hooks)
- Git tag automation in CI on merge to main
- Build hash / commit SHA appended to version (`1.2.0+abc1234`)
- Version display in additional UI locations (settings page, support email signatures)
- Linking the UI badge to the corresponding GitHub release
