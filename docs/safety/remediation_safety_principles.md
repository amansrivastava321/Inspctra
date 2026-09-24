# Remediation Safety Principles

Current remediation in QA-AI is planning-oriented and permission-gated.

## Present behavior

1. remediation outputs are plans, not auto-applied code changes
2. approval and dry-run flags explicitly control apply readiness
3. retest + regression guard are first-class checkpoints around remediation plans

## Forward principle

Future autonomous remediation must remain:

1. rollback-aware
2. approval-gated
3. artifact-traceable (who/what/when/why)
4. regression-verified before acceptance
