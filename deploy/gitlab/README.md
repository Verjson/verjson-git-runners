# Restricted GitLab runner canary

`runner.json` is the secret-free Kubernetes deployment reviewed for the shared
GitLab/Nexus host. It creates the `verjson-runners` namespace, restricted admission,
finite quota, explicit network policies, manager-only RBAC and the Nexus-pinned
GitLab Runner 18.3.1 manager. Job pods use the unprivileged `default` service account
without an automatically mounted token. The manager uses its separately named
service account to manage jobs in this namespace.

The deployment owner supplies the existing Secret
`verjson-gitlab-runner-config` containing `config.toml`; credentials and the
registered runner token must never enter this repository. Generate the
credential-free portion with `scripts/gitlab_build_config.py` from the reviewed
Nexus publication contract, including `.verjson/runtime-candidate.json`, then
supply the approved GitLab URL and runner token through the deployment's secret
management path. Do not merge it into a permissive existing runner configuration.

GitLab Runner 18.3.1 requires the fixed advanced PodSpec merge patch to set
`securityContext.seccompProfile.type: RuntimeDefault`. The generated patch only
adds that scalar subtree; it does not replace container lists or remove runner
security settings. The scripts/logs directories use `/tmp` for nonroot execution,
and job label overrides are disabled so jobs cannot acquire the manager's
network-policy label. Restricted Pod Security Admission remains enforced even
when a job attempts feature-flag overrides.

Before applying the manifest, inventory every existing NetworkPolicy in
`verjson-runners` and stop if any additional policy grants job pods manager-only
API access or broader egress. Kubernetes combines allowed traffic across matching
policies: applying a restrictive new policy cannot cancel an old broad grant.
Back up and explicitly reconcile legacy policies with the deployment owner before
continuing. Then review the exact image digests, namespace quotas,
network destinations, RBAC and the Secret contents against the live deployment.
After applying it, inspect the actual admitted job pod and verify clone, artifacts,
UID, seccomp, image restrictions, resource limits and cleanup. Publication also
requires the separately approved OIDC broker and plan/evidence acceptance; this
manifest contains no registry publisher credentials or broker deployment.

The live K3s canary observed a policy convergence window for newly created pods:
initial TCP connections to the Kubernetes API succeeded, while unauthenticated
pod/Secret requests returned HTTP 401; a later probe found both API connections
denied. The observed 20-second interval is diagnostic, not a security guarantee or
an authorization delay to rely on. Do not claim immediate TCP isolation. The
startup privilege boundary is the absence of a mounted service-account token,
unprivileged job service account and restricted Pod Security Admission. Preserve
those controls and verify actual network behavior for each deployment. Sanitized
canary evidence is recorded with the live acceptance handoff in issue #201.

GitLab's matching-version and PodSpec configuration references:

- https://docs.gitlab.com/runner/#gitlab-runner-versions
- https://docs.gitlab.com/runner/configuration/advanced-configuration/#override-the-helper-image
- https://gitlab.com/gitlab-org/gitlab-runner/-/blob/v18.3.1/docs/executors/kubernetes/_index.md
- https://gitlab.com/gitlab-org/gitlab-runner/-/blob/v18.3.1/common/config.go
