# Non-production worker deployment onboarding

Tracked in [#197](https://github.com/Verjson/verjson-git-runners/issues/197).
This is an incomplete adopter: do not merge or dispatch it until the canonical
contract test passes with real reviewed inputs. No canary, failure-stop, retry or
rollback receipt has been produced by this change.

## Reviewed target and observed gaps

| Identity | Verified value on 2026-09-09 |
| --- | --- |
| DigitalOcean team | `verJSON Common`, `ee0af667-f6af-45e4-9a75-0fce948561ab` |
| Development project | `verjson-ci`, `d5afdb31-f018-4996-b11d-37a577f92252` |
| Droplet | `596126740`, `134.209.171.181` |
| Cloud and OS hostname | `gha-deployment-canary` (formerly `gha-general-10`) |
| GitHub registration | Runner `512`, still `gha-general-10` |
| Observed runner group | `DigitalOcean`, group `8` |
| Intended admission group | Existing `verjson-runner-canary`, group `11`, currently empty |
| Current image | `ghcr.io/verjson/gha-runner-pwsh@sha256:902d2ec891a7179474b2af4b0504aa389d8f8a2754118d3e2eb29c46f4df4c06` |

The intended group restricts scheduling to the canonical runner-canary workflow at
`v1.0.1`. Inspect its live workflow policy and resolve an immutable workflow commit
before implementing the exact routed probe. Docker configuration names the intended
group but the GitHub control plane still reports group 8; configuration text is not
admission evidence. Reconcile the registration and container name through the
controlled runner lifecycle before enabling the reviewed fleet selector.

Only this host is authorized. The generated controller requires
`minimumAvailable >= 1` and at least one more fleet member than that minimum.
Obtain explicit authorization for a second existing non-production host and verify
its project, lane, identity, baseline and group before adding it to the config.
Do not lower the floor or include unrelated production capacity.

## Missing trust roots and adapters

Create three distinct, repository-scoped code/security/AI review publisher Apps
and record their actual numeric App and installation IDs in `reviewAuthority`.
Record the actual terminal-green AI source check App ID and exact check name after
verifying that check's role; an unrelated existing App is not a substitute.
The null config values are intentional missing inputs, never usable defaults.

### Publisher provisioning

These three independent private GitHub Apps are required by canonical ADR 0144. Each requests repository Checks write only (GitHub also supplies Metadata read), has no webhook, and must be installed on **only `Verjson/verjson-git-runners`** for this proof. Do not substitute existing broad organization Apps.

| Role | Prefilled GitHub registration | Protected environment | Client ID variable | Private-key secret |
| --- | --- | --- | --- | --- |
| code | [Register runner-deploy-code-review](https://github.com/organizations/Verjson/settings/apps/new?name=runner-deploy-code-review&description=Publish+canonical+code+review+receipts+for+runner+deployment&url=https%3A%2F%2Fgithub.com%2FVerjson%2Fverjson-git-runners&public=false&webhook_active=false&checks=write) | `runner-deploy-code-review-publisher` | `RUNNER_DEPLOY_CODE_REVIEW_APP_CLIENT_ID` | `RUNNER_DEPLOY_CODE_REVIEW_APP_PRIVATE_KEY` |
| security | [Register runner-deploy-security-review](https://github.com/organizations/Verjson/settings/apps/new?name=runner-deploy-security-review&description=Publish+canonical+security+review+receipts+for+runner+deployment&url=https%3A%2F%2Fgithub.com%2FVerjson%2Fverjson-git-runners&public=false&webhook_active=false&checks=write) | `runner-deploy-security-review-publisher` | `RUNNER_DEPLOY_SECURITY_REVIEW_APP_CLIENT_ID` | `RUNNER_DEPLOY_SECURITY_REVIEW_APP_PRIVATE_KEY` |
| ai | [Register runner-deploy-ai-review](https://github.com/organizations/Verjson/settings/apps/new?name=runner-deploy-ai-review&description=Publish+canonical+ai+review+receipts+for+runner+deployment&url=https%3A%2F%2Fgithub.com%2FVerjson%2Fverjson-git-runners&public=false&webhook_active=false&checks=write) | `runner-deploy-ai-review-publisher` | `RUNNER_DEPLOY_AI_REVIEW_APP_CLIENT_ID` | `RUNNER_DEPLOY_AI_REVIEW_APP_PRIVATE_KEY` |

For each App, record the distinct numeric App ID and installation ID for reviewed `container-deployment.json`. Generate a private key in the GitHub App settings and supply it directly to its matching environment secret using `gh secret set <SECRET_NAME> --repo Verjson/verjson-git-runners --env <ENVIRONMENT> < /secure/path/to/key.pem`. Never paste keys into chat, issues, or PRs. Do not use the registration App key for a review publisher.

The three publisher environments must allow protected branches only and have no wait timer, reviewer, or custom protection rules; the canonical workflow performs its own identity and provenance checks before credential admission. `production` keeps its existing review rule until the reviewed deployment configuration, three App publishers, independent review receipts, and host plan are ready for activation. Creating these Apps does not itself authorize a deployment.

The AI publisher's source authority is separately pinned to the live `ai-review-authorization` App (numeric App ID 4528902); its exact source check name must be verified from an actual trusted green check before activation. Code and security reviews require distinct eligible principals, independent of each other and the dispatcher, as specified by ADR 0144.

Registration uses GitHub's documented [prefilled registration parameters](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-using-url-parameters). The registering operator must review the prefilled permissions and selected-repository installation before submitting.

Implement the consumer-owned scripts declared by `evidenceCommand` and
`probeCommand` only after their evidence sources are established. They are absent
deliberately; this draft does not create fake successful evidence. Required work:

- Verify release manifest provenance and immutable image digests, exact live fleet
  membership, group/labels/tools, deployed baseline and available capacity.
  The upstream repair plans `manifestBytes` for exact UTF-8 release-asset text
  alongside the parsed `manifest`, and per-host `releaseManifestBytes` for baseline
  reconciliation. Once that repair lands and the adopter is regenerated, adapters
  must preserve the original bytes, bind their digest to the attested identity,
  and verify the parsed object matches. Do not reserialize JSON as asset evidence.
- Retrieve retained plans and complete receipt chains using artifact identity and
  digest; bind the exact workflow attempt, head/tree, manifest and transaction.
- Produce bounded live post-update evidence and reconcile uncertain mutation
  outcomes without retrying an unverified transition.
- Route a bounded probe to the exact named admitted runner, prove execution on that
  runner and return the verified probe result. Keep both privileged credentials
  outside probe, receipt and artifact processes.

## Release identity and proof

The observed v0.2.1 image matches release `377997930`, manifest asset `532627568`.
Its historical source is `Verjson/verjson-github-runner` at
`9e081b15e216fd33ea991daef84a156f4b03d6d2`; its release signer contract is
`4704880d1a4234dd70d06ee03be0dc8e389cee5c`. Preserve those signed identities.

The raw downloaded manifest digest is
`sha256:4f5bb96e1fe07f7b56cfe124206ed85c4e59b9715b3b4e18b3054d890dd1ad32`.
The controller's sorted compact JSON digest (UTF-8, no trailing newline) is
`sha256:cb3d413b928468fee715a7545567854455ab1b5fde88f701d0454ede2dae7532`.
These differ. The authenticated GitHub attestation DSSE subject binds the raw
asset digest. The current deployment controller expects the compact canonical
digest instead, so admission requires an upstream contract resolution tracked
under organization #629 and then regeneration at the reviewed repaired pin.
An image match alone does not establish deployable release provenance. Do not
rewrite a published asset to make a digest match.

After the gaps above are resolved, run `bash scripts/container-deployment-contract.test.sh`
and the pinned controller/preflight/review-producer behavioral suites. Then follow
the [canonical runbook at the installed pin](https://github.com/Verjson/.github/blob/55576f7cf8659d49aa28b3fca8039b6e05d47231/docs/container-deployment-runbook.md):
produce a mutation-free exact-host dry-run plan, successful canary observation,
failed-canary stop before a second update, retry/idempotency evidence and a new
independently admitted rollback to the exact previous manifest/image digest.
Retain and verify every receipt revision and its workflow URL before reporting
completion to organization #629 or closing #197.
