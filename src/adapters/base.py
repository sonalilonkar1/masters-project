"""Base adapter contract for TraceAdvisor datasets."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping
import pandas as pd
from src.canonical.schema import DatasetCapabilities
from .validation import validate_adapter_output

@dataclass(frozen=True)
class AdapterResult:
    canonical: pd.DataFrame
    metadata: Mapping[str, Any]

class BaseDatasetAdapter(ABC):
    adapter_name: str = "base"
    adapter_version: str = "0.1.0"

    @property
    @abstractmethod
    def capabilities(self) -> DatasetCapabilities:
        ...

    @abstractmethod
    def to_canonical(self, source: pd.DataFrame) -> pd.DataFrame:
        ...

    def build_metadata(self, *, source: pd.DataFrame, canonical: pd.DataFrame) -> Mapping[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "dataset_id": self.capabilities.dataset_id,
            "source_row_count": int(len(source)),
            "canonical_row_count": int(len(canonical)),
            "capabilities": self.capabilities.to_dict(),
        }

    def adapt(self, source: pd.DataFrame) -> AdapterResult:
        if not isinstance(source, pd.DataFrame):
            raise TypeError("source must be a pandas DataFrame")

        original = source.copy(deep=True)
        canonical = self.to_canonical(source.copy(deep=True))

        if not isinstance(canonical, pd.DataFrame):
            raise TypeError("to_canonical() must return a pandas DataFrame")

        pd.testing.assert_frame_equal(source, original, check_dtype=True, check_like=False)
        validate_adapter_output(canonical, capabilities=self.capabilities)

        return AdapterResult(
            canonical=canonical,
            metadata=self.build_metadata(source=source, canonical=canonical),
        )
