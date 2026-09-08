#!/usr/bin/env python3
import copy
import importlib.util
import json
import unittest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('producer_plan', ROOT / 'scripts/producer_plan.py')
producer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(producer)


class ProducerPlanTest(unittest.TestCase):
    def setUp(self):
        self.manifest = (ROOT / 'RELEASES/containers/v0.2.1.json').read_bytes()
        self.verification = (ROOT / '.verjson/release-v0.2.1-verification.json').read_bytes()
        self.targets = json.loads((ROOT / '.verjson/producer-destinations.json').read_bytes())
        self.commit = 'a' * 40
        self.receipt = {'dispatchCommit': self.commit, 'result': 'passed', 'checks': ['fixture']}

    def assemble(self, **overrides):
        args = dict(manifest_raw=self.manifest, verification_raw=self.verification,
                    test_receipt=self.receipt, commit=self.commit, destinations=self.targets)
        args.update(overrides)
        return producer.assemble(**args)

    def test_plan_preserves_signed_historical_identity_and_binds_dispatch_evidence(self):
        plan, inventory = self.assemble()
        self.assertEqual(plan['sourceRepository'], 'https://github.com/Verjson/verjson-github-runner')
        self.assertEqual(plan['sourceCommit'], '9e081b15e216fd33ea991daef84a156f4b03d6d2')
        self.assertEqual(plan['dispatchCommit'], self.commit)
        self.assertEqual(len(plan['images']), 6)
        self.assertEqual(plan['licenseInventoryDigest'], producer.digest(producer.encode(inventory)))
        self.assertEqual(plan['testReceiptDigest'], producer.digest(producer.encode(self.receipt)))
        self.assertIn('not a license clearance', inventory['scope'])
        for image in plan['images']:
            self.assertTrue(image['source'].endswith('@' + image['digest']))
            self.assertTrue(image['destination'].endswith(':0.2.1'))

    def test_modified_signed_bytes_are_denied_even_when_json_is_equivalent(self):
        with self.assertRaisesRegex(ValueError, 'signed bytes'):
            self.assemble(manifest_raw=self.manifest + b'\n')

    def test_forged_verification_receipt_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'public evidence'):
            self.assemble(verification_raw=self.verification + b'\n')

    def test_failed_or_other_commit_tests_cannot_authorize_a_plan(self):
        for receipt in [dict(self.receipt, result='failed'), dict(self.receipt, dispatchCommit='b' * 40)]:
            with self.subTest(receipt=receipt), self.assertRaisesRegex(ValueError, 'successful dispatch'):
                self.assemble(test_receipt=receipt)

    def test_destination_omissions_and_wrong_release_versions_are_denied(self):
        missing = copy.deepcopy(self.targets)
        del missing['base']
        wrong = dict(self.targets, base=self.targets['base'].replace(':0.2.1', ':9.0.0'))
        for targets in [missing, wrong]:
            with self.subTest(targets=targets), self.assertRaises(ValueError):
                self.assemble(destinations=targets)

    def test_thin_include_uses_reviewed_runtime_and_signed_producer_go_digest(self):
        include = yaml.safe_load((ROOT / '.gitlab-ci.yml').read_text())['include'][0]
        runtime = json.loads((ROOT / '.verjson/runtime-candidate.json').read_bytes())
        manifest = json.loads(self.manifest)
        go = next(image for image in manifest['images'] if image['variant'] == 'go')
        self.assertEqual(include['project'], 'Verjson/verjson-ci')
        self.assertEqual(include['ref'], runtime['sourceCommit'])
        self.assertEqual(include['file'], '/templates/producer.yml')
        self.assertEqual(include['inputs']['runtime-image'], runtime['destination'])
        self.assertEqual(include['inputs']['test-image'], self.targets['go'].rsplit(':', 1)[0] + '@' + go['indexDigest'])
        self.assertEqual(include['inputs']['test-command'], 'scripts/verify-gitlab.sh')

    def test_mutable_dispatch_reference_is_denied(self):
        with self.assertRaisesRegex(ValueError, 'immutable SHA'):
            self.assemble(commit='main')


if __name__ == '__main__':
    unittest.main()
