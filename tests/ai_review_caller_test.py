#!/usr/bin/env python3
import re
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
# This repository is on three contracts at once, so one `CONTRACT` constant
# cannot describe it and a test built on one silently asserts the wrong thing
# about two of them. Name each family's pin separately; a family that moves
# then fails here loudly instead of borrowing a sibling's SHA.
AI_CALLER_CONTRACT = 'aecfb93232db21c708ffee4b07da55d95b3a79f2'
GENERATED_ARTIFACTS_CONTRACT = '55576f7cf8659d49aa28b3fca8039b6e05d47231'
CONTAINER_CONTRACT = '3b83ddeaa421e60005e15d36e946e2f83832bacb'


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
        self.assertEqual(job['uses'], 'Verjson/.github/.github/workflows/ai-review-merge.yml@' + AI_CALLER_CONTRACT)
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
            'ai-review-merge.yml': AI_CALLER_CONTRACT,
            'gate-rearm.yml': AI_CALLER_CONTRACT,
            'generated-artifacts.yml': GENERATED_ARTIFACTS_CONTRACT,
            'container-candidate.yml': CONTAINER_CONTRACT,
            'container-candidate-publish.yml': CONTAINER_CONTRACT,
            'container-release.yml': CONTAINER_CONTRACT,
        }
        pattern = re.compile(
            r'Verjson/\.github/\.github/workflows/([a-z-]+\.yml)@([0-9a-f]{40})')
        seen = set()
        for path in sorted((ROOT / '.github/workflows').glob('*.yml')):
            for callee, sha in pattern.findall(path.read_text()):
                seen.add(callee)
                self.assertIn(callee, families,
                              f'{path.name} calls unregistered {callee}@{sha}')
                self.assertEqual(
                    sha, families[callee],
                    f'{path.name} pins {callee} outside its declared family')
        self.assertEqual(seen, set(families),
                         'the family map lists a callee nothing invokes')


if __name__ == '__main__':
    unittest.main()
