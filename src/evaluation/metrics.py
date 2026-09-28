"""
Shared resource-evaluation metrics.

This module defines the official formulas used to compare actual resource
usage with recommended resource allocations.

The functions work for:
- Google data
- Alibaba data
- Other future datasets
- Any recommendation method, such as Request, P95, ML, or Hybrid

The functions do not depend on:
- execution_id
- recurrence_key
- collection_id
- instance_index
- dataset-specific column names

The caller must provide actual and recommended values in compatible units.
"""

from __future__ import annotations

import numpy as np


# A recommendation at or below this value is treated as zero.
#
# This is mainly used for utilization because dividing by zero or an
# extremely small recommendation can produce infinity or an unrealistic
# utilization value.
DEFAULT_EPSILON = 1e-12


def cpu_violation(actual_cpu, recommended_cpu):
    """
    Check whether actual CPU usage exceeded recommended CPU.

    Formula:

        CPU violation = actual CPU > recommended CPU

    Examples:

        actual_cpu = 2, recommended_cpu = 4
        result = False

        actual_cpu = 5, recommended_cpu = 4
        result = True
    """

    # Return True when actual CPU is greater than recommended CPU.
    return np.asarray(actual_cpu) > np.asarray(recommended_cpu)


def memory_violation(actual_memory, recommended_memory):
    """
    Check whether actual memory usage exceeded recommended memory.

    Formula:

        Memory violation = actual memory > recommended memory

    Examples:

        actual_memory = 4, recommended_memory = 8
        result = False

        actual_memory = 10, recommended_memory = 8
        result = True
    """

    # Return True when actual memory is greater than recommended memory.
    return np.asarray(actual_memory) > np.asarray(recommended_memory)


def any_resource_violation(
    actual_cpu,
    recommended_cpu,
    actual_memory,
    recommended_memory,
):
    """
    Check whether either CPU or memory was under-provisioned.

    Formula:

        Any-resource violation =
            CPU violation OR Memory violation
    """

    # First calculate the CPU violation result.
    cpu_is_violated = cpu_violation(
        actual_cpu,
        recommended_cpu,
    )

    # Then calculate the memory violation result.
    memory_is_violated = memory_violation(
        actual_memory,
        recommended_memory,
    )

    # A row is violated if either resource is violated.
    return cpu_is_violated | memory_is_violated


def bounded_utilization(
    actual,
    recommended,
    epsilon: float = DEFAULT_EPSILON,
):
    """
    Calculate utilization and cap it at 100%.

    Formula:

        utilization = min(actual / recommended, 1.0)

    Examples:

        actual = 2, recommended = 4
        utilization = 0.50, or 50%

        actual = 5, recommended = 4
        raw utilization = 1.25
        bounded utilization = 1.00, or 100%

    If the recommendation is zero or extremely small, utilization is
    undefined. In that case, this function returns NaN instead of infinity.
    """

    # Convert both inputs to floating-point NumPy arrays.
    #
    # This allows the function to work with:
    # - single numeric values
    # - Python lists
    # - NumPy arrays
    # - pandas Series
    actual_array = np.asarray(actual, dtype=float)
    recommended_array = np.asarray(recommended, dtype=float)

    # Make the two arrays compatible with each other.
    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    # Start with NaN for every result.
    #
    # Rows with invalid values or zero recommendations will remain NaN.
    utilization = np.full(
        actual_array.shape,
        np.nan,
        dtype=float,
    )

    # Utilization can be calculated only when:
    # - actual is a finite number
    # - recommended is a finite number
    # - recommended is greater than epsilon
    valid_values = (
        np.isfinite(actual_array)
        & np.isfinite(recommended_array)
        & (recommended_array > epsilon)
    )

    # Calculate actual / recommended only for valid rows.
    #
    # The "where" condition prevents division by zero.
    np.divide(
        actual_array,
        recommended_array,
        out=utilization,
        where=valid_values,
    )

    # Cap the result at 1.0 so utilization never exceeds 100%.
    return np.minimum(utilization, 1.0)


def cpu_utilization(
    actual_cpu,
    recommended_cpu,
    epsilon: float = DEFAULT_EPSILON,
):
    """
    Calculate bounded CPU utilization.

    Formula:

        CPU utilization =
            min(actual CPU / recommended CPU, 1.0)
    """

    # Use the shared utilization logic for CPU.
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

    Formula:

        Memory utilization =
            min(actual memory / recommended memory, 1.0)
    """

    # Use the shared utilization logic for memory.
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

    Examples:

        actual = 6, recommended = 10
        waste = 4

        actual = 12, recommended = 10
        waste = 0
    """

    # Convert both values to floating-point arrays.
    actual_array = np.asarray(actual, dtype=float)
    recommended_array = np.asarray(recommended, dtype=float)

    # Make the input shapes compatible.
    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    # Waste is positive only when the recommendation exceeds actual usage.
    #
    # If actual usage is greater than the recommendation, waste is zero.
    return np.maximum(
        recommended_array - actual_array,
        0.0,
    )


def shortfall(actual, recommended):
    """
    Calculate how much actual usage exceeded the recommendation.

    Formula:

        shortfall = max(actual - recommended, 0)

    Examples:

        actual = 6, recommended = 10
        shortfall = 0

        actual = 12, recommended = 10
        shortfall = 2
    """

    # Convert both values to floating-point arrays.
    actual_array = np.asarray(actual, dtype=float)
    recommended_array = np.asarray(recommended, dtype=float)

    # Make the input shapes compatible.
    actual_array, recommended_array = np.broadcast_arrays(
        actual_array,
        recommended_array,
    )

    # Shortfall is positive only when actual usage exceeds the recommendation.
    #
    # If the recommendation is greater than actual usage, shortfall is zero.
    return np.maximum(
        actual_array - recommended_array,
        0.0,
    )