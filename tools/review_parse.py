"""Read LAST_REVIEW from one mission block; never infer a passing review."""
import re
from datetime import datetime


def parse_review(block: str) -> dict:
    reviews = []
    for value in re.findall(r'^\s*LAST_REVIEW:\s*(.+)$', block, re.M):
        value = re.sub(r'^[\w.-]+:\s+', '', value.strip())
        match = re.fullmatch(r'(.+?)\s+(PASS|FAIL)\s+(\S+)', value)
        if not match:
            continue
        path, verdict, at = match.groups()
        try:
            stamp = datetime.fromisoformat(at.replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                continue
        except ValueError:
            continue
        reviews.append((stamp, {'verdict': verdict, 'path': path, 'at': at}))
    review = max(reviews, key=lambda item: item[0])[1].copy() if reviews else {'verdict': 'none'}
    status_values = re.findall(r'^[ \t]*(?:STATUS|ACCEPTED_CHECKPOINT):[ \t]*([^\n]*)$', block, re.M)
    verified = any(re.search(r'\bVERIFIED\b', value) for value in status_values)
    if verified and review['verdict'] == 'FAIL':
        review['verdict'] = 'fail'
    elif verified and review['verdict'] == 'none':
        review['verdict'] = 'verified_without_review'
    return review
