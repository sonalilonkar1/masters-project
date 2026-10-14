# TraceAdvisor Dataset Adapter Framework

**New Development Issue 3**

## Goal
Separate dataset-specific ingestion and transformation from shared TraceAdvisor logic.

## Contract
Every production adapter subclasses `BaseDatasetAdapter` and provides:
- `capabilities`
- `to_canonical(source)`
- optional adapter-specific metadata

`BaseDatasetAdapter.adapt()` copies the source, invokes mapping, verifies a DataFrame is returned, verifies the caller-owned source was not mutated, validates the canonical result, and returns canonical data plus metadata.

## Adapters own
- raw source column names
- source parsing
- timestamp conversion
- verified unit mapping/conversion
- source-specific ID construction
- traceability metadata

## Adapters do not own
- historical percentile policies
- ML predictions
- Hybrid policy decisions
- violation/utilization/waste/shortfall metrics
- evaluator summaries
- final-test decisions

## Validation
`validate_adapter_output()` enforces:
- unique canonical columns
- exactly one expected dataset ID
- finite resource values when populated
- canonical schema validation
- dataset capability restrictions
- preservation of null/unsupported values

No validation helper fills missing values with zero.

## Reference adapter
`ReferenceOccurrenceAdapter` exists only to exercise the framework contract. It is not a production Google, Alibaba, or Azure adapter.

## Issue boundary
Issue 3 ends with the shared adapter framework and contract tests.
Issue 4 implements Alibaba and Azure VM adapters and canonical integration artifacts.
