# Alibaba GPU 2020 canonical build: count report

Code commit: `c2ae87f4aa357384a3cc8bdc72f776f1012c3ab7` (dirty: False)

## Rows

| Output | Rows |
|---|---|
| role_occurrence | 1,254,108 |
| instance | 7,410,783 |
| rejected | 121,824 |

| Rejected level | Reason | Rows |
|---|---|---|
| instance | missing_submission_time | 111,219 |
| job | missing_submission_time | 3,663 |
| role_occurrence | missing_submission_time | 6,942 |

## Reconciliation (source = accepted + rejected)

| Level | Source table | Source | Accepted | Rejected | Difference |
|---|---|---|---|---|---|
| job | `pai_job_table` | 1,055,501 | 1,051,838 | 3,663 | 0 |
| role_occurrence | `pai_task_table` | 1,261,050 | 1,254,108 | 6,942 | 0 |
| instance | `pai_instance_table` | 7,522,002 | 7,410,783 | 111,219 | 0 |

Every level reconciles.

## Exclusion reasons (role_occurrence, rule order)

| `exclusion_reason` | Roles |
|---|---|
| `no_recurrence_key` | 1,788 |
| `job_failed` | 282,027 |
| `job_incomplete` | 87,980 |
| `task_not_terminated` | 0 |
| `missing_or_invalid_request` | 2 |
| `instance_failed` | 33,022 |
| `instance_interrupted` | 31 |
| `instance_incomplete` | 0 |
| `missing_worker_name` | 0 |
| `multi_attempt_worker` | 2,048 |
| `missing_sensor` | 287,780 |
| `partial_sensor_coverage` | 97,018 |
| `invalid_memory_exceeds_capacity` | 512 |
| `invalid_resource` | 0 |
| `<null>` | 461,900 |

## Eligibility summary

| Field | Roles |
|---|---|
| accepted_roles | 1,254,108 |
| pass_all_but_multi_attempt_worker | 462,156 |
| eligible | 461,900 |
| eligible_missing_cpu | 1,224 |

## Validity

Row validity:

| View | Status | Rows |
|---|---|---|
| role_occurrence | valid | 677,334 |
| role_occurrence | partial | 574,793 |
| role_occurrence | invalid | 1,981 |
| instance | partial | 4,384,687 |
| instance | valid | 3,020,973 |
| instance | invalid | 5,123 |

CPU validity:

| View | Status | Rows |
|---|---|---|
| role_occurrence | valid | 675,914 |
| role_occurrence | partial | 578,194 |
| instance | partial | 4,389,291 |
| instance | valid | 3,021,492 |

Memory validity:

| View | Status | Rows |
|---|---|---|
| role_occurrence | valid | 677,334 |
| role_occurrence | partial | 574,793 |
| role_occurrence | invalid | 1,981 |
| instance | partial | 4,384,687 |
| instance | valid | 3,020,973 |
| instance | invalid | 5,123 |

## Join coverage

| Join | driving_matched | driving_null_key | driving_unmatched | lookup_unused | lookup_used |
|---|---|---|---|---|---|
| job_group_tag | 1,053,971 | 0 | 1,530 | 1,061 | 1,053,971 |
| task_job | 1,261,050 | 0 | 0 | 0 | 1,055,501 |
| instance_task | 7,522,002 | 0 | 0 | 130 | 1,260,920 |
| instance_sensor | 3,027,318 | 331,057 | 4,494,684 | 13,883 | 3,019,349 |
| instance_machine_spec | 7,190,945 | 331,057 | 331,057 | 0 | 1,897 |

## Expected versus actual

| Figure | Expected | Actual | Difference |
|---|---|---|---|
| rows: role_occurrence | 1,254,108 | 1,254,108 | 0 |
| rows: instance | 7,410,783 | 7,410,783 | 0 |
| rows: rejected | 121,824 | 121,824 | 0 |
| rejected: job | 3,663 | 3,663 | 0 |
| rejected: role_occurrence | 6,942 | 6,942 | 0 |
| rejected: instance | 111,219 | 111,219 | 0 |
| exclusion: no_recurrence_key | 1,788 | 1,788 | 0 |
| exclusion: job_failed | 282,027 | 282,027 | 0 |
| exclusion: job_incomplete | 87,980 | 87,980 | 0 |
| exclusion: task_not_terminated | 0 | 0 | 0 |
| exclusion: missing_or_invalid_request | 2 | 2 | 0 |
| exclusion: instance_failed | 33,022 | 33,022 | 0 |
| exclusion: instance_interrupted | 31 | 31 | 0 |
| exclusion: instance_incomplete | 0 | 0 | 0 |
| exclusion: missing_worker_name | 0 | 0 | 0 |
| exclusion: multi_attempt_worker | 2,048 | 2,048 | 0 |
| exclusion: missing_sensor | 287,780 | 287,780 | 0 |
| exclusion: partial_sensor_coverage | 97,018 | 97,018 | 0 |
| exclusion: invalid_memory_exceeds_capacity | 512 | 512 | 0 |
| exclusion: invalid_resource | 0 | 0 | 0 |
| exclusion: <null> | 461,900 | 461,900 | 0 |
| eligibility: accepted_roles | 1,254,108 | 1,254,108 | 0 |
| eligibility: pass_all_but_multi_attempt_worker | 462,156 | 462,156 | 0 |
| eligibility: eligible | 461,900 | 461,900 | 0 |
| eligibility: eligible_missing_cpu | 1,224 | 1,224 | 0 |

All differences are zero.
