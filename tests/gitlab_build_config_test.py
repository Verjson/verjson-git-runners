import copy
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
