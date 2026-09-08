#!/usr/bin/env python3
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = '55576f7cf8659d49aa28b3fca8039b6e05d47231'


class ReviewCallerTest(unittest.TestCase):
    def test_required_org_arm_has_no_duplicate_consumer_dispatcher(self):
        self.assertFalse((ROOT / '.github/workflows/gate-rearm.yml').exists())
        caller = yaml.safe_load((ROOT / '.github/workflows/ai-review-label-rearm.yml').read_text())
        events = caller[True]['pull_request_target']['types']
        self.assertEqual(set(events), {'labeled', 'ready_for_review', 'converted_to_draft', 'edited', 'unlabeled'})
        self.assertFalse({'opened', 'synchronize', 'reopened'} & set(events))
        self.assertEqual(caller['jobs']['rearm']['uses'], 'Verjson/.github/.github/workflows/gate-rearm.yml@' + CONTRACT)

    def test_review_dispatch_keeps_exact_head_inputs_with_repaired_immutable_contract(self):
        caller = yaml.safe_load((ROOT / '.github/workflows/ai-review-merge.yml').read_text())
        job = caller['jobs']['review']
        self.assertEqual(job['uses'], 'Verjson/.github/.github/workflows/ai-review-merge.yml@' + CONTRACT)
        self.assertEqual(job['with']['expected_head_sha'], '${{ inputs.expected_head_sha }}')
        self.assertEqual(job['with']['authorization_check_id'], '${{ inputs.authorization_check_id }}')
        self.assertEqual(job['with']['arm_run_id'], '${{ inputs.arm_run_id }}')


if __name__ == '__main__':
    unittest.main()
