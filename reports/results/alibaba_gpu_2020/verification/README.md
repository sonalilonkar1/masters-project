# Alibaba GPU 2020 verification outputs

This directory is populated by:

```bash
python scripts/verify_alibaba_gpu_2020_artifacts.py
```

Expected generated files:

- `artifact_manifest.json`
- `verification_report.md`
- `reproduction_metadata.json`

These are verification evidence only. They must not contain new model selection, tuning, or final-test scoring.
