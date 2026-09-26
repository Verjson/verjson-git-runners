#!/usr/bin/env python3
import hashlib
import json
import re
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
# This repository is on three contracts at once, so one `CONTRACT` constant
# cannot describe it and a test built on one silently asserts the wrong thing
# about two of them. The pins live in tests/contract_pins.json so that the shell
# contract test reads the same values; a second copy is how this repository last
# asserted the wrong contract.
_PINS = json.loads((ROOT / 'tests/contract_pins.json').read_text())
AI_CALLER_CONTRACT = _PINS['ai-callers']
AI_REVIEW_CONTRACT = _PINS['ai-review-merge']
GENERATED_ARTIFACTS_CONTRACT = _PINS['generated-artifacts']
CONTAINER_CONTRACT = _PINS['containers']
CONTAINER_DEPLOYMENT_CONTRACT = _PINS['container-deployment']

# Under `secrets: inherit` the caller names no secret, so nothing in its text
# bounds what it hands the callee. Byte identity is what is left: these are
# generated files, and a digest change means the generator's output changed or
# somebody hand-edited a privileged caller. The privileged-merge pair is pinned
# the same way in tests/privileged_merge_caller_contract_test.sh.
GENERATED_CALLER_DIGESTS = {
    '.github/workflows/ai-review-merge.yml':
        'eac19a2a2d8c811618e3bca541f9344bbfee8b180330882e8073932106e4149f',
    '.github/workflows/ai-review-label-rearm.yml':
        '62bbb760f54229db79465c7803aa93bed38bf95d66192bb4e4ecea0006eebe59',
}


class ReviewCallerTest(unittest.TestCase):
    def test_required_org_arm_has_no_duplicate_consumer_dispatcher(self):
        self.assertFalse((ROOT / '.github/workflows/gate-rearm.yml').exists())
        caller = yaml.safe_load((ROOT / '.github/workflows/ai-review-label-rearm.yml').read_text())
        events = caller[True]['pull_request_target']['types']
        self.assertEqual(set(events), {'labeled', 'ready_for_review', 'converted_to_draft', 'edited', 'unlabeled'})
        self.assertFalse({'opened', 'synchronize', 'reopened'} & set(events))
        self.assertEqual(caller['jobs']['rearm']['uses'], 'Verjson/.github/.github/workflows/gate-rearm.yml@' + AI_CALLER_CONTRACT)

    def test_review_dispatch_keeps_exact_head_inputs_with_repaired_immutable_contract(self):
        caller = yaml.safe_load((ROOT / '.github/workflows/ai-review-merge.yml').read_text())
        job = caller['jobs']['review']
        self.assertEqual(job['uses'], 'Verjson/.github/.github/workflows/ai-review-merge.yml@' + AI_REVIEW_CONTRACT)
        self.assertEqual(job['with']['expected_head_sha'], '${{ inputs.expected_head_sha }}')
        self.assertEqual(job['with']['authorization_check_id'], '${{ inputs.authorization_check_id }}')
        self.assertEqual(job['with']['arm_run_id'], '${{ inputs.arm_run_id }}')


    def test_every_hub_caller_is_pinned_to_its_declared_family(self):
        """No caller drifts to a SHA this repository has not named.

        The three constants above are the whole inventory. A caller repinned
        without updating them lands here rather than in a reviewer's memory,
        which is the failure this repository has already had twice.
        """
        families = {
            'ai-privileged-merge.yml': AI_CALLER_CONTRACT,
            'ai-promotion-retry.yml': AI_CALLER_CONTRACT,
            'ai-review-merge.yml': AI_REVIEW_CONTRACT,
            'gate-rearm.yml': AI_CALLER_CONTRACT,
            'generated-artifacts.yml': GENERATED_ARTIFACTS_CONTRACT,
            'container-candidate.yml': CONTAINER_CONTRACT,
            'container-candidate-publish.yml': CONTAINER_CONTRACT,
            'container-release.yml': CONTAINER_CONTRACT,
            'container-deployment.yml': CONTAINER_DEPLOYMENT_CONTRACT,
            'container-deployment-review-producer.yml': CONTAINER_DEPLOYMENT_CONTRACT,
        }
        # A narrow callee pattern does not fail on a name it cannot match — it
        # skips it, so a caller named outside the pattern escapes the whole
        # check silently. Match permissively, then assert that every reference
        # to a hub workflow in the tree was one this pattern consumed.
        pattern = re.compile(
            r'Verjson/\.github/\.github/workflows/([A-Za-z0-9._-]+\.ya?ml)@([0-9a-f]{40})')
        any_reference = re.compile(r'Verjson/\.github/\.github/workflows/\S+')
        seen = set()
        for path in sorted((ROOT / '.github/workflows').glob('*.y*ml')):
            text = path.read_text()
            matched = {m.group(0) for m in pattern.finditer(text)}
            for reference in any_reference.findall(text):
                reference = reference.rstrip("'\",")
                self.assertTrue(
                    any(reference.startswith(m) or m.startswith(reference)
                        for m in matched),
                    f'{path.name} references {reference}, which is not a '
                    'pinned hub caller this test can check')
            for callee, sha in pattern.findall(text):
                seen.add(callee)
                self.assertIn(callee, families,
                              f'{path.name} calls unregistered {callee}@{sha}')
                self.assertEqual(
                    sha, families[callee],
                    f'{path.name} pins {callee} outside its declared family')
        self.assertEqual(seen, set(families),
                         'the family map lists a callee nothing invokes')

    def test_generated_ai_review_callers_are_byte_pinned(self):
        """A privileged caller cannot change without this test saying so."""
        for relative, expected in GENERATED_CALLER_DIGESTS.items():
            with self.subTest(caller=relative):
                digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(
                    expected, digest,
                    f'{relative} changed; regenerate it with the canonical '
                    'generator and repin this digest deliberately')


if __name__ == '__main__':
    unittest.main()
