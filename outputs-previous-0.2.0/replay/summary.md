# Scripted integration replay

**This is not a broad capability benchmark. Demo runs do not call a language model.**

| Case | Provider | Held-out test exit | Resolved | Tool calls | Wall time (s) |
|---|---|---:|---|---:|---:|
| redis | demo | 0 | True | 7 | 11.10 |
| pagination | demo | 0 | True | 7 | 10.70 |
| normalize | demo | 0 | True | 7 | 10.57 |

See each case's trace, patch, test output, and report for evidence.

## Limitations

- Three small synthetic Python tasks; not representative of real GitHub issues
- Demo actions are predefined; demo resolution rate is not model accuracy
- Timing includes process startup and evaluation approvals
- Public fixture/reference code may create training or inspection contamination
