from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping
import pandas as pd

# 0.2.0 extends 0.1.0: nothing is removed or renamed. Every adapter writes this
# constant, so they all emit 0.2.0 without an adapter change.
SCHEMA_VERSION = "0.2.0"
# role_occurrence (0.2.0): one role of one job occurrence, for example the
# "worker" or "ps" role of an Alibaba GPU 2020 job. It is the evaluation row
# for Alibaba GPU 2020 and is identified by role_key (schema §4.1).
RECORD_LEVELS = {"workload","occurrence","role_occurrence","execution","instance","interval"}
TIME_BASES = {"unix_epoch","trace_relative","unknown"}
VALIDITY_STATUSES = {"valid","partial","invalid","unknown","unsupported"}
CORE_REQUIRED_COLUMNS = {"schema_version","dataset_id","record_level","workload_id","time_basis","validity_status"}
RESOURCE_VALUE_FIELDS = [
    "requested_cpu","requested_memory","allocated_cpu","allocated_memory",
    "observed_cpu","observed_memory","peak_cpu","peak_memory",
    "actual_cpu","actual_memory","recommended_cpu","recommended_memory",
    # GPU fields (0.2.0, schema §6.4): descriptive only. Listing them here
    # gives them the same unit, numeric and non-negative checks as CPU and
    # memory. There is no GPU capability flag; GPU evaluation is out of scope.
    "requested_gpu","observed_gpu","peak_gpu_memory",
]
RESOURCE_UNIT_FIELDS = {f: f"{f}_unit" for f in RESOURCE_VALUE_FIELDS}

ALLOWED_RESOURCE_UNITS = {
    "ncu",
    "normalized",
    "cpu_core",
    "vcpu",
    "gb",
    "percent",
    "alibaba_plan_cpu_100_per_core",
    "alibaba_cpu_usage_source_unit",
    "alibaba_memory_source_normalized",
    # 0.2.0 (schema §6.2): Alibaba GPU 2020 reports CPU and GPU as a percentage
    # of one device, where 100 means one full vCPU or one full GPU.
    "percent_of_vcpu",
    "percent_of_gpu",
}

# ---------------------------------------------------------------------------
# Vocabularies added in schema 0.2.0.
# Each set lists the only values a column or profile field may hold, so a typo
# (for example "availble") fails validation instead of passing silently.
# ---------------------------------------------------------------------------

# What one resource value covers (schema §8). Alibaba GPU 2020 role rows are
# task_role_per_instance: the request is per instance, not a job total.
RESOURCE_SCOPES = {"full_workload", "task_role_per_instance", "instance", "job_total"}

# How a request value was built from source rows (schema §8).
# descriptive_job_total marks totals kept for description only, never targets.
REQUEST_AGGREGATION_METHODS = {"sum_over_executions", "none", "descriptive_job_total"}

# How an observed value was built from source rows (schema §8).
OBSERVED_AGGREGATION_METHODS = {"aligned_window_sum_then_maximum", "maximum_over_instances", "none"}

# Why a next-occurrence target is or isn't available (schema §11).
# Written by the Task 4 target builder, read by the Task 5 evaluator.
TARGET_STATUSES = {
    "available",
    "no_next_occurrence",
    "next_occurrence_in_other_split",
    "next_occurrence_ineligible_resource",
    "unsupported_resource",
}

# Where a dataset's recurrence_key comes from (schema §10.2):
#   constructed        - built by the pipeline (Google)
#   official           - a source identifier used as is
#   official_with_role - a source identifier plus the task role (Alibaba GPU 2020)
#   none               - no recurrence key; recurrence_key must stay null
RECURRENCE_KEY_ORIGINS = {"constructed", "official", "official_with_role", "none"}

# How the evaluator scores a dataset (schema §10.2).
# next_occurrence_memory_peak_cpu_average: memory peak is the primary target and
# CPU is a lifetime average (Alibaba GPU 2020).
EVALUATION_MODES = {
    "full_next_occurrence",
    "next_occurrence_memory_peak_cpu_average",
    "instance_request_versus_observed",
}

# What an observed or peak resource value means (schema §7).
RESOURCE_SEMANTICS = {"window_peak", "lifetime_peak", "lifetime_average", "instance_peak", "instance_average"}

# What a next-occurrence target value means (schema §7).
TARGET_SEMANTICS = {"next_occurrence_peak", "next_occurrence_lifetime_average", "next_occurrence_lifetime_peak"}

# What the row's main timestamp means (schema §7).
TIME_SEMANTICS = {"first_execution_start", "job_submission", "instance_start"}

# What event_time_us means on instance rows (schema §7). parent_job_submission:
# the instance row carries its parent job's submission time, so event_time_us
# becomes required on instance rows for profiles that declare it.
INSTANCE_EVENT_TIME_SEMANTICS = {"parent_job_submission"}

# Alibaba GPU 2020 exclusion reasons in rule order (schema §9.3). The adapter
# applies the rules in this order, and the first failed rule sets
# exclusion_reason. A tuple keeps the order.
ALIBABA_GPU_2020_EXCLUSION_REASONS = (
    "no_recurrence_key",
    "job_failed",
    "job_incomplete",
    "task_not_terminated",
    "missing_or_invalid_request",
    "instance_failed",
    "instance_interrupted",
    "instance_incomplete",
    "missing_worker_name",
    "multi_attempt_worker",
    "missing_sensor",
    "partial_sensor_coverage",
    "invalid_memory_exceeds_capacity",
    "invalid_resource",
)


class CanonicalSchemaError(ValueError):
    # Defined before DatasetCapabilities so __post_init__ can raise it.
    pass


@dataclass(frozen=True)
class DatasetCapabilities:
    """What a dataset can provide, and how its values are to be read.

    The first eleven fields are the 0.1.0 profile and are passed positionally
    by the existing profiles below. Every 0.2.0 field comes after ``notes``
    and has a default, so those positional calls keep working and an unedited
    profile (Azure) behaves exactly as in 0.1.0.
    """

    # --- 0.1.0 fields (unchanged) -------------------------------------------
    dataset_id: str
    supports_cpu: bool
    supports_memory: bool
    supports_request: bool
    supports_recurrence: bool
    supports_targets: bool
    supports_ml: bool
    supports_observed_cpu: bool
    supports_observed_memory: bool
    supports_allocated_cpu: bool
    supports_allocated_memory: bool
    notes: str = ""

    # --- 0.2.0: average versus peak (schema §10.2) ---------------------------
    # In 0.1.0, supports_observed_cpu allowed observed_cpu (average) and
    # peak_cpu together. These flags separate them, so Alibaba GPU 2020 can
    # have an average CPU but no CPU peak.
    # None means "not given": __post_init__ then copies supports_observed_cpu
    # (or supports_observed_memory), which reproduces the 0.1.0 behavior.
    has_cpu_average: bool | None = None
    has_cpu_peak: bool | None = None
    has_memory_average: bool | None = None
    has_memory_peak: bool | None = None

    # --- 0.2.0: identity and meaning of values (schema §7, §10.2) ------------
    recurrence_key_origin: str = "none"          # one of RECURRENCE_KEY_ORIGINS
    observed_cpu_semantics: str | None = None    # RESOURCE_SEMANTICS
    peak_cpu_semantics: str | None = None
    observed_memory_semantics: str | None = None
    peak_memory_semantics: str | None = None
    cpu_target_semantics: str | None = None      # TARGET_SEMANTICS
    memory_target_semantics: str | None = None
    time_semantics: str | None = None            # TIME_SEMANTICS
    instance_event_time_semantics: str | None = None  # INSTANCE_EVENT_TIME_SEMANTICS
    cpu_unit: str | None = None                  # null or in ALLOWED_RESOURCE_UNITS
    memory_unit: str | None = None
    telemetry_window: str | None = None          # free text, e.g. "Full 31-day subset"

    # --- 0.2.0: record levels and evaluation (schema §10.2) ------------------
    # None means no restriction: any record level in RECORD_LEVELS is allowed.
    supported_record_levels: tuple[str, ...] | None = None
    evaluation_record_level: str | None = None   # level the evaluator scores
    evaluation_mode: str | None = None           # one of EVALUATION_MODES

    # Empty means the dataset has no exclusion rules: every exclusion_reason
    # must be null.
    allowed_exclusion_reasons: tuple[str, ...] = ()

    # False tells the evaluator (Task 5) not to report any-resource metrics.
    any_resource_metric_valid: bool = True
    # True tells the target builder (Task 4) that a target must come from the
    # same split as its row.
    target_split_isolation: bool = False

    def __post_init__(self) -> None:
        # The dataclass is frozen, so fields are set with object.__setattr__.

        # 1. Fill the average/peak flags that were not given.
        for name, source in (
            ("has_cpu_average", self.supports_observed_cpu),
            ("has_cpu_peak", self.supports_observed_cpu),
            ("has_memory_average", self.supports_observed_memory),
            ("has_memory_peak", self.supports_observed_memory),
        ):
            if getattr(self, name) is None:
                object.__setattr__(self, name, source)

        # Accept lists for the sequence fields, but store tuples so the
        # frozen profile stays immutable.
        if self.supported_record_levels is not None:
            object.__setattr__(self, "supported_record_levels", tuple(self.supported_record_levels))
        object.__setattr__(self, "allowed_exclusion_reasons", tuple(self.allowed_exclusion_reasons))

        # 2. Consistency rules (schema §10.2): "observed CPU is supported" must
        # mean "an average or a peak CPU exists", and the same for memory.
        # supports_cpu never implies a CPU peak, so it is not used here.
        if self.supports_observed_cpu != (self.has_cpu_average or self.has_cpu_peak):
            raise CanonicalSchemaError(
                f"{self.dataset_id}: supports_observed_cpu must equal "
                "has_cpu_average or has_cpu_peak"
            )
        if self.supports_observed_memory != (self.has_memory_average or self.has_memory_peak):
            raise CanonicalSchemaError(
                f"{self.dataset_id}: supports_observed_memory must equal "
                "has_memory_average or has_memory_peak"
            )

        # 3. Every declared value must come from its vocabulary, so a wrong
        # profile fails when it is created rather than during validation.
        self._check_value("recurrence_key_origin", RECURRENCE_KEY_ORIGINS, allow_null=False)
        for name in ("observed_cpu_semantics", "peak_cpu_semantics",
                     "observed_memory_semantics", "peak_memory_semantics"):
            self._check_value(name, RESOURCE_SEMANTICS)
        for name in ("cpu_target_semantics", "memory_target_semantics"):
            self._check_value(name, TARGET_SEMANTICS)
        self._check_value("time_semantics", TIME_SEMANTICS)
        self._check_value("instance_event_time_semantics", INSTANCE_EVENT_TIME_SEMANTICS)
        self._check_value("cpu_unit", ALLOWED_RESOURCE_UNITS)
        self._check_value("memory_unit", ALLOWED_RESOURCE_UNITS)
        self._check_value("evaluation_record_level", RECORD_LEVELS)
        self._check_value("evaluation_mode", EVALUATION_MODES)
        if self.supported_record_levels is not None:
            unknown = sorted(set(self.supported_record_levels) - RECORD_LEVELS)
            if unknown:
                raise CanonicalSchemaError(
                    f"{self.dataset_id}: unknown supported_record_levels {unknown}"
                )

    def _check_value(self, name: str, allowed: set, *, allow_null: bool = True) -> None:
        """Raise if profile field ``name`` is not in ``allowed`` (null is allowed unless told otherwise)."""
        value = getattr(self, name)
        if value is None and allow_null:
            return
        if value not in allowed:
            raise CanonicalSchemaError(f"{self.dataset_id}: unsupported {name} {value!r}")

    def to_dict(self) -> dict:
        # asdict() keeps tuples, but JSON loads arrays as lists, and a tuple
        # never equals a list. Convert so the registry test can compare this
        # dict with config/dataset_capabilities.json.
        data = asdict(self)
        for name in ("supported_record_levels", "allowed_exclusion_reasons"):
            if data[name] is not None:
                data[name] = list(data[name])
        return data

# Profile values follow schema §10.3. The positional 0.1.0 arguments are
# unchanged; 0.2.0 values are added as keyword arguments.

GOOGLE_CAPABILITIES = DatasetCapabilities(
    "google_clusterdata2019", True, True, True, True, True, True,
    True, True, False, False,
    "Reference corrected Google occurrence pipeline.",
    # Google occurrence artifacts hold peaks only (no averages), so a
    # populated observed_cpu or observed_memory is rejected.
    has_cpu_average=False,
    has_cpu_peak=True,
    has_memory_average=False,
    has_memory_peak=True,
    recurrence_key_origin="constructed",
    peak_cpu_semantics="window_peak",
    peak_memory_semantics="window_peak",
    cpu_target_semantics="next_occurrence_peak",
    memory_target_semantics="next_occurrence_peak",
    time_semantics="first_execution_start",
    cpu_unit="ncu",
    memory_unit="normalized",
    telemetry_window="Full 31-day subset",
    supported_record_levels=("occurrence",),
    evaluation_record_level="occurrence",
    evaluation_mode="full_next_occurrence",
    any_resource_metric_valid=True,
    # Current Google targets may cross splits; corrected separately (Task 10).
    target_split_isolation=False,
)
ALIBABA_CAPABILITIES = DatasetCapabilities(
    "alibaba_clustertrace2018", True, True, True, False, False, False,
    True, True, False, False,
    "Recurrence/targets remain disabled until a derived rule is validated.",
    has_cpu_average=True,
    has_cpu_peak=True,
    has_memory_average=True,
    has_memory_peak=True,
    recurrence_key_origin="none",
    observed_cpu_semantics="instance_average",
    peak_cpu_semantics="instance_peak",
    observed_memory_semantics="instance_average",
    peak_memory_semantics="instance_peak",
    time_semantics="instance_start",
    # CPU request and CPU usage use two different source units, so no single
    # cpu_unit is true; it stays null.
    cpu_unit=None,
    memory_unit="alibaba_memory_source_normalized",
    telemetry_window="Full trace",
    supported_record_levels=("instance",),
    evaluation_record_level="instance",
    evaluation_mode="instance_request_versus_observed",
    # any_resource_metric_valid and target_split_isolation keep their
    # defaults: Alibaba 2018 has no targets, so they have no effect.
)
# Azure is deliberately not edited: the 0.2.0 defaults reproduce its 0.1.0
# behavior (has_cpu_* True, has_memory_* False, no record-level restriction,
# recurrence_key_origin "none").
AZURE_VM_CAPABILITIES = DatasetCapabilities(
    "azure_public_vm_v2", True, True, False, False, False, False,
    True, False, True, True,
    "CPU telemetry and VM capacity supported; observed memory unavailable."
)
ALIBABA_GPU_2020_CAPABILITIES = DatasetCapabilities(
    "alibaba_gpu_v2020", True, True, True, True, True, True,
    True, True, False, False,
    "Required second integration. Role-level next-occurrence evaluation; "
    "memory peak primary, CPU lifetime average only.",
    # The trace has a lifetime-average CPU but no CPU peak, so a populated
    # peak_cpu (which would be an average mislabeled as a peak) is rejected.
    has_cpu_average=True,
    has_cpu_peak=False,
    has_memory_average=True,
    has_memory_peak=True,
    # The official "group" identifier plus the task role.
    recurrence_key_origin="official_with_role",
    observed_cpu_semantics="lifetime_average",
    peak_cpu_semantics=None,
    observed_memory_semantics="lifetime_average",
    peak_memory_semantics="lifetime_peak",
    cpu_target_semantics="next_occurrence_lifetime_average",
    memory_target_semantics="next_occurrence_lifetime_peak",
    time_semantics="job_submission",
    # Instance rows carry the parent job's submission time, which makes
    # event_time_us required on instance rows.
    instance_event_time_semantics="parent_job_submission",
    cpu_unit="percent_of_vcpu",
    memory_unit="gb",
    telemetry_window="About day 19 to day 68.9",
    # role_occurrence rows are evaluated; instance rows are kept for audit.
    supported_record_levels=("role_occurrence", "instance"),
    evaluation_record_level="role_occurrence",
    evaluation_mode="next_occurrence_memory_peak_cpu_average",
    allowed_exclusion_reasons=ALIBABA_GPU_2020_EXCLUSION_REASONS,
    # CPU (average) and memory (peak) mean different things, so a combined
    # any-resource violation is not meaningful.
    any_resource_metric_valid=False,
    # Targets must come from the same split as their row.
    target_split_isolation=True,
)
DEFAULT_CAPABILITY_REGISTRY = {x.dataset_id: x for x in (
    GOOGLE_CAPABILITIES, ALIBABA_CAPABILITIES, AZURE_VM_CAPABILITIES,
    ALIBABA_GPU_2020_CAPABILITIES,
)}

def records_to_frame(records: Iterable[Mapping]) -> pd.DataFrame:
    return pd.DataFrame(list(records))

def _nonnull(df, col):
    return df[col].notna() if col in df.columns else pd.Series(False, index=df.index)

def _reject_populated(df, cols, reason):
    bad = [c for c in cols if c in df.columns and df[c].notna().any()]
    if bad:
        raise CanonicalSchemaError(f"Unsupported fields populated ({reason}): {bad}")

def validate_canonical_frame(df: pd.DataFrame, capabilities: DatasetCapabilities) -> None:
    missing = sorted(CORE_REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise CanonicalSchemaError(f"Missing required columns: {missing}")
    if df.empty:
        return
    if (df["schema_version"] != SCHEMA_VERSION).any():
        raise CanonicalSchemaError(f"Expected schema_version={SCHEMA_VERSION}")
    if (df["dataset_id"] != capabilities.dataset_id).any():
        raise CanonicalSchemaError("dataset_id does not match capability specification")
    if (~df["record_level"].isin(RECORD_LEVELS)).any():
        raise CanonicalSchemaError("Unsupported record_level")
    if (~df["time_basis"].isin(TIME_BASES)).any():
        raise CanonicalSchemaError("Unsupported time_basis")
    if (~df["validity_status"].isin(VALIDITY_STATUSES)).any():
        raise CanonicalSchemaError("Unsupported validity_status")
    if df["workload_id"].isna().any():
        raise CanonicalSchemaError("workload_id must not be null")
    if (~(_nonnull(df,"event_time_us") | _nonnull(df,"start_time_us"))).any():
        raise CanonicalSchemaError("Each row needs event_time_us or start_time_us")
    if "start_time_us" in df.columns and "end_time_us" in df.columns:
        mask = df["start_time_us"].notna() & df["end_time_us"].notna()
        if (mask & (pd.to_numeric(df["end_time_us"], errors="coerce") < pd.to_numeric(df["start_time_us"], errors="coerce"))).any():
            raise CanonicalSchemaError("end_time_us must be >= start_time_us")
    for value_col, unit_col in RESOURCE_UNIT_FIELDS.items():
        if value_col not in df.columns:
            continue
        supplied = df[value_col].notna()
        vals = pd.to_numeric(df[value_col], errors="coerce")
        if (supplied & vals.isna()).any():
            raise CanonicalSchemaError(
                f"{value_col} contains non-numeric values"
            )
        if (supplied & (vals < 0)).any():
            raise CanonicalSchemaError(
                f"{value_col} must be non-negative"
            )
        if supplied.any():
            if (
                unit_col not in df.columns
                or (supplied & df[unit_col].isna()).any()
            ):
                raise CanonicalSchemaError(
                    f"{unit_col} required whenever {value_col} is populated"
                )

            units = df.loc[supplied, unit_col].astype("string")
            invalid_units = ~units.isin(ALLOWED_RESOURCE_UNITS)

            if invalid_units.any():
                bad_units = sorted(
                    units.loc[invalid_units].dropna().unique().tolist()
                )
                raise CanonicalSchemaError(
                    f"{unit_col} contains unsupported units: {bad_units}"
                )
    if not capabilities.supports_cpu:
        _reject_populated(
            df,
            [
                "requested_cpu",
                "allocated_cpu",
                "observed_cpu",
                "peak_cpu",
                "actual_cpu",
                "recommended_cpu",
            ],
            "CPU unsupported",
        )

    if not capabilities.supports_memory:
        _reject_populated(
            df,
            [
                "requested_memory",
                "allocated_memory",
                "observed_memory",
                "peak_memory",
                "actual_memory",
                "recommended_memory",
            ],
            "memory unsupported",
        )

    if not capabilities.supports_recurrence:
        _reject_populated(
            df,
            ["recurrence_key"],
            "recurrence unsupported",
        )

    if not capabilities.supports_request:
        _reject_populated(
            df,
            ["requested_cpu", "requested_memory"],
            "request unsupported",
        )

    if not capabilities.supports_targets:
        _reject_populated(
            df,
            ["actual_cpu", "actual_memory"],
            "targets unsupported",
        )

    if not capabilities.supports_observed_cpu:
        _reject_populated(
            df,
            ["observed_cpu", "peak_cpu"],
            "observed CPU unsupported",
        )

    if not capabilities.supports_observed_memory:
        _reject_populated(
            df,
            ["observed_memory", "peak_memory"],
            "observed memory unsupported",
        )

    if not capabilities.supports_allocated_cpu:
        _reject_populated(
            df,
            ["allocated_cpu"],
            "allocated CPU unsupported",
        )

    if not capabilities.supports_allocated_memory:
        _reject_populated(
            df,
            ["allocated_memory"],
            "allocated memory unsupported",
        )

    # -----------------------------------------------------------------------
    # 0.2.0 checks. They run after every 0.1.0 check, so frames that broke a
    # 0.1.0 rule still fail with the same message as before.
    # -----------------------------------------------------------------------

    # Average versus peak (schema §9.2, §10.2). The supports_observed_* gates
    # above allow or block average and peak together; these block each kind
    # on its own. For Alibaba GPU 2020, has_cpu_peak is False, so a populated
    # peak_cpu (an average mislabeled as a peak) is rejected here.
    if not capabilities.has_cpu_average:
        _reject_populated(df, ["observed_cpu"], "CPU average unsupported")
    if not capabilities.has_cpu_peak:
        _reject_populated(df, ["peak_cpu"], "CPU peak unsupported")
    if not capabilities.has_memory_average:
        _reject_populated(df, ["observed_memory"], "memory average unsupported")
    if not capabilities.has_memory_peak:
        _reject_populated(df, ["peak_memory"], "memory peak unsupported")

    # Record levels the profile allows. None means no restriction (Azure).
    if capabilities.supported_record_levels is not None:
        _check_vocabulary(df, "record_level", set(capabilities.supported_record_levels))

    # Column vocabularies. Each check runs only when its column is present,
    # and only on non-null values, so 0.1.0-shaped frames still pass.
    _check_vocabulary(df, "cpu_validity_status", VALIDITY_STATUSES)
    _check_vocabulary(df, "memory_validity_status", VALIDITY_STATUSES)
    _check_vocabulary(df, "resource_scope", RESOURCE_SCOPES)
    _check_vocabulary(df, "request_aggregation_method", REQUEST_AGGREGATION_METHODS)
    _check_vocabulary(df, "observed_aggregation_method", OBSERVED_AGGREGATION_METHODS)
    _check_vocabulary(df, "cpu_target_status", TARGET_STATUSES)
    _check_vocabulary(df, "memory_target_status", TARGET_STATUSES)

    # exclusion_reason must be one of the profile's reasons. A profile with no
    # reasons (Google, Alibaba 2018, Azure) therefore allows only nulls.
    _check_vocabulary(df, "exclusion_reason", set(capabilities.allowed_exclusion_reasons))

    # Instance rows of a profile with instance_event_time_semantics =
    # parent_job_submission (Alibaba GPU 2020) must carry event_time_us: the
    # parent job's submission time. Profiles that don't declare it (Alibaba
    # 2018, Azure) keep the 0.1.0 rule (event_time_us or start_time_us).
    if capabilities.instance_event_time_semantics == "parent_job_submission":
        instance_rows = df["record_level"] == "instance"
        if (instance_rows & ~_nonnull(df, "event_time_us")).any():
            raise CanonicalSchemaError(
                "event_time_us required on instance rows when "
                "instance_event_time_semantics is parent_job_submission"
            )


def _check_vocabulary(df: pd.DataFrame, col: str, allowed: set) -> None:
    """Raise if column ``col`` holds a non-null value outside ``allowed``.

    An absent column passes, so frames that don't use the column are not
    affected.
    """
    if col not in df.columns:
        return
    values = df[col].dropna()
    bad = sorted(values[~values.isin(allowed)].astype(str).unique().tolist())
    if bad:
        raise CanonicalSchemaError(f"Unsupported {col} values: {bad}")


def validate_evaluator_view(df: pd.DataFrame) -> None:
    required = {
        "dataset_id","workload_id","policy_name",
        "actual_cpu","actual_memory","recommended_cpu","recommended_memory",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise CanonicalSchemaError(f"Missing evaluator columns: {missing}")
    cpu_pair = df["actual_cpu"].notna() & df["recommended_cpu"].notna()
    mem_pair = df["actual_memory"].notna() & df["recommended_memory"].notna()
    if (~(cpu_pair | mem_pair)).any():
        raise CanonicalSchemaError("Each evaluator row needs at least one actual/recommendation pair")
    for resource, pair in (("cpu",cpu_pair),("memory",mem_pair)):
        if not pair.any():
            continue
        au, ru = f"actual_{resource}_unit", f"recommended_{resource}_unit"
        if au not in df.columns or ru not in df.columns:
            raise CanonicalSchemaError(f"Unit columns required for {resource}")
        # Every evaluated pair needs explicit units on both values.
        missing_units = pair & (df[au].isna() | df[ru].isna())
        if missing_units.any():
            raise CanonicalSchemaError(
                f"{resource} actual/recommendation units must be populated"
            )

        # Compare unit strings only after ruling out missing values.
        mismatched_units = pair & (
            df[au].astype("string") != df[ru].astype("string")
        )
        if mismatched_units.any():
            raise CanonicalSchemaError(
                f"{resource} actual/recommendation units must match"
            )