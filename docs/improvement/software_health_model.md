# Software Health Model

`SoftwareHealthModel` computes a weighted quality score across audit and runtime dimensions.

## Dimensions

Current weighted signals include security, code quality, runtime, release, sync, database, evidence, and regression.

## Outputs

`software_health_score` includes:

1. overall score
2. health level
3. per-dimension weighted breakdown
4. recommendation text

This score feeds backlog prioritization and summary/reporting layers.
