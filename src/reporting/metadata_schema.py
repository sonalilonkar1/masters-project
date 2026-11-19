"""Closed schemas for Task 12's reporting metadata, independent of input claims.

A trailing '?' marks a producer-defined optional property. Dictionaries are
closed recursively; annotations have one explicitly unverified extension point.
Historical Task 8 metadata is read, never rewritten, and retains nullable fields.
"""
import json

from src.canonical.schema import DEFAULT_CAPABILITY_REGISTRY

ALIBABA = 'alibaba_gpu_v2020'
GOOGLE = 'google_clusterdata2019'
DATASETS = {ALIBABA, GOOGLE, 'azure_public_vm_v2', 'alibaba_clustertrace2018'}
ANNOTATIONS = {'scope': frozenset({'unverified'}), 'notes': [str]}
IDENTITY = dict.fromkeys(('decision_manifest_sha256', 'run_id', 'code_commit'), str)
SOURCE = dict.fromkeys(('path', 'path_base', 'sha256'), str)
REFERENCE = {**SOURCE, 'role': str}
OUTPUT = dict.fromkeys(('path', 'sha256'), str)
BINDING = dict.fromkeys(('dataset_id', 'logical_artifact', 'stage', 'manifest_path', 'published_path', 'sha256'), str)
ENVIRONMENT = dict.fromkeys(('python', 'pandas', 'matplotlib', 'numpy', 'pyarrow'), str)
TRACEABILITY = dict.fromkeys(('unique_source_metric_cells', 'rendered_metric_cells', 'conclusion_metric_cells'), int)
SCOPE = dict.fromkeys(('published_reporting_bytes', 'published_metadata', 'external_physical_artifact_bytes',
    'historical_execution', 'model_inference_reproduction', 'task4_test_value_isolation', 'configuration_annotations'), str)
DECISION = dict.fromkeys(('dataset_id', 'decision_status', 'outcome', 'decision_summary', 'record_sha256', 'evidence_sha256'), str)

SPEC = {'completion': str, 'decision_status': str, 'decision_outcome': str,
        'decision_record': str, 'decision_evidence': [str],
        'evidence?': [str], 'followup_evidence?': [str], 'reason?': str, 'annotation?': str, 'limitations?': [str],
        'unverified_annotations?': ANNOTATIONS,
        **{name + '?': str for name in ('decision_summary', 'approval_reference', 'metadata', 'results', 'sensitivity',
            'verification_manifest', 'verification_manifest_sha256', 'run_record', 'run_log', 'run_log_sha256',
            'final_metadata', 'decision_manifest', 'producer_dataset_id')},
        'expected_identity?': IDENTITY, 'artifact_bindings?': [BINDING],
        'expected_artifacts?': dict.fromkeys(('metadata', 'results', 'run_record', 'decision_manifest'), str)}
CONFIGURATION = {'report_version': int, 'datasets': {dataset: SPEC for dataset in DATASETS},
                 'report_name?': str, 'historical_report?': str, 'unverified_annotations?': ANNOTATIONS}
RECORD = {'schema_version': int, **dict.fromkeys(('dataset_id', 'status', 'outcome', 'summary', 'evidence_path', 'evidence_sha256'), str),
          'approval_reference?': str, 'approval_sha256?': str}
EVIDENCE = {**dict.fromkeys(('dataset_id', 'status', 'outcome', 'basis'), str),
            'approval_reference?': str, 'approval_sha256?': str}
APPROVAL = {'schema_version': int, **dict.fromkeys(('dataset_id', 'status', 'outcome', 'approval_reference', 'summary'), str)}
TASK8_ENVIRONMENT = {**dict.fromkeys(('dataset_id', 'schema_version', 'python_version', 'pandas_version',
    'verification_command', 'full_test_command', 'generated_utc', 'generation_id', 'verification_status'), str),
    'code_commit': (str, type(None)), 'code_dirty': (bool, type(None))}
ALIBABA_EVIDENCE = {**dict.fromkeys(('dataset_id', 'generation_id', 'manifest_sha256', 'published_metadata_consistency',
    'published_artifact_bytes', 'external_physical_artifact_bytes', 'historical_exactly_once_execution',
    'scientific_inference_reproduction', 'november_10_byte_equivalence'), str),
    'identity': IDENTITY, 'bindings': [{**BINDING, 'observed_sha256': str, 'verification': str}],
    'unverified_items': [{'item': str, 'reason': str}], 'final_population_size': int,
    'upstream_reporting_environment': TASK8_ENVIRONMENT, 'followups': [str]}
GOOGLE_EVIDENCE = {**dict.fromkeys(('dataset_id', 'producer_dataset_id', 'decision_manifest_sha256', 'execution_commit',
    'published_metadata_consistency', 'published_artifact_bytes', 'external_physical_artifact_bytes',
    'scientific_inference_reproduction', 'historical_exactly_once_execution'), str),
    'final_population_size': int, 'limitations': [str]}


def _producer_shape(value):
    """Profile property definitions come from trusted executing code, not a receipt."""
    if isinstance(value, dict):
        return {key: _producer_shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [str]  # Both producer-defined profile arrays contain strings.
    return type(value)


def _executable_schema():
    return {'path_base_description': str, 'files': [REFERENCE], 'capability_registry': {
        **dict.fromkeys(('configuration_source', 'definition_module', 'definition_path', 'definition_path_base', 'sha256'), str),
        'effective_profiles': {key: _producer_shape(value.to_dict())
                               for key, value in DEFAULT_CAPABILITY_REGISTRY.items()}}}


def validate_shape(value, schema, path='$'):
    if isinstance(schema, dict):
        if type(value) is not dict:
            raise ValueError(f'metadata schema: {path} must be an object')
        allowed = {key.removesuffix('?') for key in schema}
        required = {key for key in schema if not key.endswith('?')}
        extra, missing = set(value) - allowed, required - set(value)
        if extra or missing:
            raise ValueError(f'metadata schema: {path} undeclared fields={sorted(extra)} missing fields={sorted(missing)}')
        for key, item_schema in schema.items():
            name = key.removesuffix('?')
            if name in value:
                validate_shape(value[name], item_schema, f'{path}.{name}')
    elif isinstance(schema, list):
        if type(value) is not list:
            raise ValueError(f'metadata schema: {path} must be an array')
        for index, item in enumerate(value):
            validate_shape(item, schema[0], f'{path}[{index}]')
    elif isinstance(schema, frozenset):
        if type(value) is not str or value not in schema:
            raise ValueError(f'metadata schema: {path} has an unsupported literal')
    elif type(value) not in (schema if isinstance(schema, tuple) else (schema,)):
        raise ValueError(f'metadata schema: {path} has an invalid type')


def validate_configuration(config):
    validate_shape(config, CONFIGURATION, '$.configuration')


def validate_metadata(document, kind):
    """Enforce the same closed, typed contract before publication and on reading."""
    common = {'kind': str, 'configuration': CONFIGURATION, 'environment': ENVIRONMENT,
        'executable_code': _executable_schema(), 'sources': [SOURCE], 'outputs': [OUTPUT],
        'upstream_evidence': {ALIBABA: ALIBABA_EVIDENCE, GOOGLE: GOOGLE_EVIDENCE},
        'verification_scope': SCOPE, 'dataset_decisions': [DECISION],
        'reporting_status': frozenset({'COMPLETE', 'DECISION_PENDING'}), 'project_completion': bool,
        'metric_traceability': TRACEABILITY, 'unverified_annotations?': ANNOTATIONS}
    if kind == 'manifest':
        schema = {**common, 'schema_version': int, 'reporting_validation': str}
    elif kind == 'receipt':
        schema = {**common, 'reference_documents': [REFERENCE]}
    else:
        raise ValueError(f'unknown reporting metadata kind: {kind}')
    schema['kind'] = frozenset({'Task 12 reporting artifact manifest v2' if kind == 'manifest' else 'Task 12 final reporting receipt v2'})
    validate_shape(document, schema, '$.' + kind)
    if kind == 'manifest' and document['schema_version'] != 2:
        raise ValueError('metadata schema: unsupported manifest schema version')
    if document.get('unverified_annotations') != document['configuration'].get('unverified_annotations'):
        raise ValueError('metadata schema: annotation container must match configured unverified notes')


def loads(raw):
    """Reject ambiguous duplicate properties and non-JSON numeric constants."""
    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise ValueError(f'metadata schema: duplicate property {name!r}')
            result[name] = value
        return result
    def constant(value):
        raise ValueError(f'metadata schema: non-JSON constant {value}')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
