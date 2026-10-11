#!/usr/bin/env python3
"""Delivery catalog-preparation-recovery-20261010-1333 — bounded prep then browser-sync scope."""
from __future__ import annotations

import browser_sync_recovery_acceptance as bsa

bsa.DELIVERY = 'catalog-preparation-recovery-20261010-1333'
bsa.PRIOR_DELIVERY = 'browser-build-bound-correction-20261010-1320'
bsa.ISOLATED = bsa.ROOT / 'app' / '.data' / bsa.DELIVERY
bsa.CLONE = bsa.ISOLATED / 'catalog-clone'
bsa.DB = bsa.ISOLATED / 'local.sqlite'

import canonical_edit_sync_acceptance as ces  # noqa: E402

ces.DELIVERY = bsa.DELIVERY
ces.ISOLATED = bsa.ISOLATED
ces.CLONE = bsa.CLONE
ces.DB = bsa.DB

if __name__ == '__main__':
    raise SystemExit(bsa.main())
