# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import warnings
from datetime import datetime
from typing import Any

from ax.core.experiment import Experiment
from ax.core.parameter import FixedParameter
from ax.exceptions.core import AxWarning
from ax.modelbridge.generation_strategy import GenerationStep, GenerationStrategy
from ax.modelbridge.modelbridge_utils import (
    extract_search_space_digest,
    transform_search_space,
)
from ax.modelbridge.registry import ModelRegistryBase, Models, SearchSpace
from ax.modelbridge.transforms.base import Transform
from ax.modelbridge.transforms.cast import Cast

# Models whose generated trails will count towards initialization_trials
INITIALIZATION_MODELS: list[Models] = [Models.SOBOL, Models.UNIFORM]

# Models whose generated trails will count towards other_trials
OTHER_MODELS: list[Models] = []
# Product surface to use if none is provided
DEFAULT_PRODUCT_SURFACE = "unknown"


def _get_max_transformed_dimensionality(
    search_space: SearchSpace, generation_strategy: GenerationStrategy
) -> int | None:
    """
    Get dimensionality of transformed SearchSpace for all steps in the
    GenerationStrategy and return the maximum.
    """
    if generation_strategy.is_node_based:
        warnings.warn(
            "`_get_max_transformed_dimensionality` does not fully support node-based "
            "generation strategies. This will result in an incomplete record.",
            category=AxWarning,
            stacklevel=4,
        )
        # TODO [T192965545]: Support node-based generation strategies in telemetry
        return None

    transforms_by_step = [
        _extract_transforms_and_configs(step=step)
        for step in generation_strategy._steps
    ]

    transformed_search_spaces = [
        transform_search_space(
            search_space=search_space,
            transforms=[Cast] + transforms,
            transform_configs=transform_configs,
        )
        for transforms, transform_configs in transforms_by_step
    ]

    # The length of the bounds of a SearchSpaceDigest is equal to the number of
    # dimensions present.
    dimensionalities = [
        len(
            extract_search_space_digest(
                search_space=tf_search_space,
                param_names=[
                    name
                    for name, param in tf_search_space.parameters.items()
                    if not isinstance(param, FixedParameter)
                ],
            ).bounds
        )
        for tf_search_space in transformed_search_spaces
    ]

    return max(dimensionalities)


def _extract_transforms_and_configs(
    step: GenerationStep,
) -> tuple[list[type[Transform]], dict[str, Any]]:
    """
    Extract Transforms and their configs from the GenerationStep. Prefer kwargs
    provided over the model's defaults.
    """

    kwargs = step.model_spec.model_kwargs or {}
    transforms = kwargs.get("transforms")
    transform_configs = kwargs.get("transform_configs")

    if transforms is not None and transform_configs is not None:
        return transforms, transform_configs

    model = step.model
    if isinstance(model, ModelRegistryBase):
        _, bridge_kwargs = model.view_defaults()
        transforms = transforms or bridge_kwargs.get("transforms")
        transform_configs = transform_configs or bridge_kwargs.get("transform_configs")

    return (transforms or [], transform_configs or {})


def get_unique_identifier(experiment: Experiment) -> str:
    """
    Return a unique identifier for an experiment so creation and completion
    events can be joined.
    """
    str_time = datetime.strftime(experiment.time_created, "%Y-%m-%d %H:%M:%S")
    return f"{experiment.name}_{str_time}"
