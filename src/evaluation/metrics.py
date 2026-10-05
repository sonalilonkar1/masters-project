"""
Shared resource-evaluation metrics.

This module defines the official formulas used to compare actual resource
usage with recommended resource allocations.
"""

from __future__ import annotations

import numpy as np


DEFAULT_EPSILON = 1e-12


def cpu_violation(actual_cpu, recommended_cpu):
    """
    Check whether actual CPU usage exceeded recommended CPU.

    Returns NaN when either input is non-finite.
    """
    actual_array = np.asarray(actual_cpu, dtype=float)
    recommended_array = np.asarray(recommended_cpu, dtype=float)

    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    valid_values = (
        np.isfinite(actual_array)
        & np.isfinite(recommended_array)
    )

    return np.where(
        valid_values,
        actual_array > recommended_array,
        np.nan,
    )


def memory_violation(actual_memory, recommended_memory):
    """
    Check whether actual memory usage exceeded recommended memory.

    Returns NaN when either input is non-finite.
    """
    actual_array = np.asarray(actual_memory, dtype=float)
    recommended_array = np.asarray(recommended_memory, dtype=float)

    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    valid_values = (
        np.isfinite(actual_array)
        & np.isfinite(recommended_array)
    )

    return np.where(
        valid_values,
        actual_array > recommended_array,
        np.nan,
    )


def any_resource_violation(
    actual_cpu,
    recommended_cpu,
    actual_memory,
    recommended_memory,
):
    """
    Check whether either CPU or memory was under-provisioned.

    Returns:
        1.0 if either resource definitely violates.
        0.0 if both resources are valid non-violations.
        NaN if no resource definitely violates but one is unknown.
    """
    cpu_result = cpu_violation(
        actual_cpu,
        recommended_cpu,
    )

    memory_result = memory_violation(
        actual_memory,
        recommended_memory,
    )

    cpu_result, memory_result = np.broadcast_arrays(
        cpu_result,
        memory_result,
    )

    definite_violation = (
        (cpu_result == 1.0)
        | (memory_result == 1.0)
    )

    unknown_result = (
        np.isnan(cpu_result)
        | np.isnan(memory_result)
    )

    return np.where(
        definite_violation,
        1.0,
        np.where(
            unknown_result,
            np.nan,
            0.0,
        ),
    )


def bounded_utilization(
    actual,
    recommended,
    epsilon: float = DEFAULT_EPSILON,
):
    """
    Calculate utilization and cap it at 100%.

    Returns NaN when actual or recommended is non-finite, or when the
    recommendation is zero or extremely small.
    """
    actual_array = np.asarray(actual, dtype=float)
    recommended_array = np.asarray(recommended, dtype=float)

    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    utilization = np.full(
        actual_array.shape,
        np.nan,
        dtype=float,
    )

    valid_values = (
        np.isfinite(actual_array)
        & np.isfinite(recommended_array)
        & (recommended_array > epsilon)
    )

    np.divide(
        actual_array,
        recommended_array,
        out=utilization,
        where=valid_values,
    )

    return np.minimum(utilization, 1.0)


def cpu_utilization(
    actual_cpu,
    recommended_cpu,
    epsilon: float = DEFAULT_EPSILON,
):
    """
    Calculate bounded CPU utilization.
    """
    return bounded_utilization(
        actual_cpu,
        recommended_cpu,
        epsilon=epsilon,
    )


def memory_utilization(
    actual_memory,
    recommended_memory,
    epsilon: float = DEFAULT_EPSILON,
):
    """
    Calculate bounded memory utilization.
    """
    return bounded_utilization(
        actual_memory,
        recommended_memory,
        epsilon=epsilon,
    )


def waste(actual, recommended):
    """
    Calculate unused recommended capacity.

    Formula:
        waste = max(recommended - actual, 0)
    """
    actual_array = np.asarray(actual, dtype=float)
    recommended_array = np.asarray(recommended, dtype=float)

    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    return np.maximum(
        recommended_array - actual_array,
        0.0,
    )


def shortfall(actual, recommended):
    """
    Calculate how much actual usage exceeded the recommendation.

    Formula:
        shortfall = max(actual - recommended, 0)
    """
    actual_array = np.asarray(actual, dtype=float)
    recommended_array = np.asarray(recommended, dtype=float)

    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    return np.maximum(
        actual_array - recommended_array,
        0.0,
    )