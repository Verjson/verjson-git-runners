import copy
import json
import importlib.util
from pathlib import Path
import tomllib
import unittest

spec = importlib.util.spec_from_file_location('config', Path(__file__).resolve().parents[1] / 'scripts/gitlab_build_config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def contract():
    result = {'registry': 'nexus.example.org', 'namespace': 'gitlab-jobs', 'architecture': 'amd64'}
    for index, (role, path) in enumerate((('build', 'ghcr.io/verjson/gha-runner-node'), ('manager', 'registry.gitlab.com/gitlab-org/gitlab-runner'), ('helper', 'registry.gitlab.com/gitlab-org/gitlab-runner/gitlab-runner-helper')), 1):
        digest = 'sha256:' + str(index) * 64
        result[role] = {'source': path + '@' + digest, 'destination': 'nexus.example.org/' + role + '@' + digest, 'version': '18.3.1'}
    return result


class BuildConfigTest(unittest.TestCase):
    def test_only_selected_producer_image_can_run_without_github_entrypoint(self):
        data = contract()
        runner = tomllib.loads(config.render(data))['runners'][0]
        self.assertFalse(runner['feature_flags']['FF_KUBERNETES_HONOR_ENTRYPOINT'])
        self.assertEqual(runner['kubernetes']['allowed_images'], [data['build']['destination']])
        self.assertNotIn(data['manager']['destination'], runner['kubernetes'].values())
        self.assertEqual(runner['kubernetes']['helper_image'], data['helper']['destination'])

    def test_reviewed_runtime_adds_only_its_exact_digest_to_job_allowlist(self):
        data = contract()
        data['runtime'] = {
            'sourceRepository': 'https://github.com/Verjson/verjson-ci',
            'sourceCommit': 'a' * 40,
            'destination': 'nexus.example.org/verjson/ci/candidates@sha256:' + '4' * 64,
            'artifactLicenseInventoryDigest': 'sha256:' + '5' * 64,
            'trust': 'reviewed-bootstrap-candidate',
        }
        allowed = tomllib.loads(config.render(data))['runners'][0]['kubernetes']['allowed_images']
        self.assertEqual(allowed, [data['build']['destination'], data['runtime']['destination']])
        for key, value in [
            ('sourceRepository', 'https://github.com/other/verjson-ci'),
            ('sourceCommit', 'main'),
            ('destination', 'evil.example.org/verjson/ci/candidates@sha256:' + '4' * 64),
            ('destination', 'nexus.example.org/verjson/ci/other@sha256:' + '4' * 64),
            ('destination', 'nexus.example.org/verjson/ci/candidates:latest'),
            ('artifactLicenseInventoryDigest', 'sha256:short'),
            ('trust', 'signed-stable-release'),
        ]:
            changed = copy.deepcopy(data)
            changed['runtime'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(config.ContractError):
                config.render(changed)

    def test_gitlab_183_jobs_satisfy_restricted_seccomp_without_privileged_accounts(self):
        runner = tomllib.loads(config.render(contract()))['runners'][0]
        settings = runner['kubernetes']
        self.assertTrue(runner['feature_flags']['FF_USE_ADVANCED_POD_SPEC_CONFIGURATION'])
        self.assertEqual(settings['pod_spec'][0], {
            'name': 'restricted-seccomp', 'patch_type': 'merge',
            'patch': json.dumps({'securityContext': {'seccompProfile': {'type': 'RuntimeDefault'}}}),
        })
        self.assertEqual(settings['service_account'], 'default')
        self.assertEqual(settings['pod_labels_overwrite_allowed'], '')
        self.assertEqual(settings['scripts_base_dir'], '/tmp')
        self.assertEqual(settings['logs_base_dir'], '/tmp')

    def test_nonroot_home_reaches_helper_and_build_without_replacing_containers(self):
        runner = tomllib.loads(config.render(contract()))['runners'][0]
        self.assertEqual(runner['environment'], ['HOME=/tmp'])
        patch = runner['kubernetes']['pod_spec'][1]
        self.assertEqual(patch['patch_type'], 'strategic')
        self.assertEqual(json.loads(patch['patch']), {'containers': [
            {'name': name, 'env': [{'name': 'HOME', 'value': '/tmp'}]}
            for name in ('build', 'helper')
        ]})

    def test_jobs_have_nonroot_bounded_resources_without_host_mounts_or_credentials(self):
        parsed = tomllib.loads(config.render(contract()))
        self.assertEqual(parsed['concurrent'], 1)
        settings = parsed['runners'][0]['kubernetes']
        self.assertEqual(settings['pod_security_context']['run_as_user'], 1001)
        for name in ('privileged', 'allow_privilege_escalation', 'automount_service_account_token', 'bearer_token_overwrite_allowed'):
            self.assertFalse(settings[name])
        self.assertEqual(settings['cap_drop'], ['ALL'])
        self.assertNotIn('volumes', settings)
        for prefix in ('', 'helper_'):
            for resource in ('cpu', 'memory', 'ephemeral_storage'):
                self.assertTrue(settings[prefix + resource + '_limit'])
        self.assertEqual(settings['allowed_pull_policies'], ['always'])

    def test_rejects_untrusted_mutable_or_mismatched_image_records(self):
        changes = [('build', 'destination', 'nexus.example.org/build:latest'), ('build', 'source', 'ghcr.io/other/image@sha256:' + '1' * 64), ('build', 'destination', 'evil.example.org/build@sha256:' + '1' * 64), ('build', 'destination', 'nexus.example.org/build@sha256:' + '9' * 64), ('manager', 'source', 'ghcr.io/verjson/gha-runner@sha256:' + '2' * 64), ('helper', 'version', '18.2.0'), ('helper', 'version', 'latest'), ('build', 'source', 'ghcrXio/verjson/gha-runner@sha256:' + '1' * 64), ('build', 'version', '01.2.3')]
        for role, field, value in changes:
            with self.subTest(role=role, field=field, value=value):
                data = contract()
                data[role][field] = value
                with self.assertRaises(config.ContractError):
                    config.render(data)

    def test_rejects_injection_and_unknown_settings(self):
        for field, value in [('registry', 'nexus.example.org/evil'), ('registry', 'nexus.example.org:99999'), ('namespace', 'jobs"\nprivileged=true'), ('architecture', 's390x'), ('extra', True), ('build', None)]:
            data = contract()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(config.ContractError):
                config.render(data)

    def test_arm64_uses_matching_node_selector_without_mutating_input(self):
        data = contract()
        data['architecture'] = 'arm64'
        before = copy.deepcopy(data)
        parsed = tomllib.loads(config.render(data))
        self.assertEqual(parsed['runners'][0]['kubernetes']['node_selector']['kubernetes.io/arch'], 'arm64')
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()
