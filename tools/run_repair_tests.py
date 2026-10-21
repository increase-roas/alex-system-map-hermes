#!/usr/bin/env python3
"""Run the repair and local-evidence suites once, without overlapping discovery."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
modules = sorted({path.stem for pattern in ('test_*repair*.py', 'test_local_file*.py') for path in root.glob(pattern)})
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(module) for module in modules)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
