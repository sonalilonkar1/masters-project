"""Dataset adapter framework for TraceAdvisor."""
from .base import AdapterResult, BaseDatasetAdapter
from .validation import AdapterValidationError, validate_adapter_output
from .alibaba import Alibaba2018Adapter
from .alibaba_gpu_2020 import AlibabaGPU2020Adapter
from .azure_vm import AzureVMAdapter

__all__ = [
    "AdapterResult",
    "BaseDatasetAdapter",
    "AdapterValidationError",
    "validate_adapter_output",
    "Alibaba2018Adapter",
    "AlibabaGPU2020Adapter",
    "AzureVMAdapter",
]
