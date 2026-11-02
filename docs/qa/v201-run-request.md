# Windows isolated published 2.0.1 update test run

QA only. No product changes, no merge to main, no production data.

Test: qa/test_public_main_source.py on base branch test/20261102-v201-public-source-windows.
Pinned old public main source: fa51b0123aaac76ddff2064d34178e7cc6e3ab11 (2.0.0).
Pinned public main HEAD: 31963c3c48c9d9cd95663c971a55cb3bb9b108f6 (2.0.1).
Purpose: verify official GitHub URL download, archive validation, backup, install, local isolated service start, data hashes and backup rollback on Windows. Previous separate Windows Chromium E2E covers failure-triggered rollback.

Do not merge this PR into any branch. The workflow is test-only and uses fictional temporary directories.