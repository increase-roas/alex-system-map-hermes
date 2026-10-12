"""LAST_REVIEW contract checks, without reading or writing the real ledger."""
import re
import unittest
from review_parse import parse_review

LEDGER = '''## Mission: Passed
LAST_REVIEW: ~/reviews/pass.md PASS 2026-10-12T01:00:00Z
## Mission: Failed
LAST_REVIEW: node-2: ~/reviews/fail.md FAIL 2026-10-12T02:00:00Z
## Mission: Missing
STATUS: VERIFIED
LAST_REVIEW: NONE
## Mission: Not reviewed
LAST_REVIEW: NONE
'''

class ReviewParseTests(unittest.TestCase):
    def test_four_distinct_mission_results(self):
        results = [parse_review(b) for b in re.split(r'(?m)^## Mission: ', LEDGER)[1:]]
        self.assertEqual([r['verdict'] for r in results], ['PASS', 'FAIL', 'verified_without_review', 'none'])
        self.assertEqual(results[0], {'verdict': 'PASS', 'path': '~/reviews/pass.md', 'at': '2026-10-12T01:00:00Z'})
        self.assertEqual(results[1]['path'], '~/reviews/fail.md')

    def test_latest_per_node_review_wins(self):
        self.assertEqual(parse_review('LAST_REVIEW: a: /a PASS 2026-10-12T01:00:00Z\nLAST_REVIEW: b: /b FAIL 2026-10-12T02:00:00Z')['verdict'], 'FAIL')

    def test_verified_with_failed_review_is_red(self):
        self.assertEqual(parse_review('STATUS: VERIFIED\nLAST_REVIEW: /a FAIL 2026-10-12T01:00:00Z')['verdict'], 'fail')

    def test_verified_in_acceptance_or_prose_is_not_status(self):
        for block in ['ACCEPTANCE: must be VERIFIED', 'Notes: previously VERIFIED',
                      'STATUS: ACTIVE\nACCEPTANCE: VERIFIED',
                      'STATUS:\nVERIFIED in prose']:
            with self.subTest(block=block):
                self.assertEqual(parse_review(block), {'verdict': 'none'})

    def test_verified_checkpoint_is_status(self):
        self.assertEqual(parse_review('ACCEPTED_CHECKPOINT: VERIFIED'),
                         {'verdict': 'verified_without_review'})

    def test_unverified_is_not_verified(self):
        self.assertEqual(parse_review('STATUS: UNVERIFIED'), {'verdict': 'none'})

    def test_path_with_spaces_and_bad_timestamp(self):
        self.assertEqual(parse_review('LAST_REVIEW: /my reviews/a.md PASS 2026-10-12T01:00:00Z')['path'], '/my reviews/a.md')
        self.assertEqual(parse_review('LAST_REVIEW: /a PASS nonsense'), {'verdict': 'none'})

if __name__ == '__main__':
    unittest.main()
