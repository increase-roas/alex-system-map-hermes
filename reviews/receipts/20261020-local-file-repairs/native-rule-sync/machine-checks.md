| Check | Result | Detail |
| --- | --- | --- |
| `cmd:python3 -B /private/tmp/native-rule-sync-verification/probe.py` | VERIFIED | exit 0; OK |
| `file:/tmp/native-rule-sync-final-suite.log non-empty` | VERIFIED | 3792 bytes |
| `contains:/tmp/native-rule-sync-final-suite.log::Ran 78 tests` | VERIFIED | 1 occurrence(s) |
| `contains:/tmp/native-rule-sync-final-suite.log::EXIT: 0` | VERIFIED | 1 occurrence(s) |
| `contains:/Users/alexlobaito/.agents/tools/unify/hooks/post-commit::apply --rules-only;` | VERIFIED | 1 occurrence(s) |
| `absent:/Users/alexlobaito/.agents/tools/unify/hooks/post-commit::build_instructions.py" apply;` | VERIFIED | 0 occurrence(s) |
