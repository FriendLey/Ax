#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from typing import Optional, TYPE_CHECKING

from ax.adapter.transforms.base import Transform

from ax.core.observation import Observation, ObservationFeatures
from ax.core.parameter import ParameterType, RangeParameter
from ax.core.search_space import SearchSpace
from ax.models.types import TConfig
from scipy.special import expit, logit

if TYPE_CHECKING:
    # import as module to make sphinx-autodoc-typehints happy
    from ax import adapter as adapter_module  # noqa F401


class Logit(Transform):
    """Apply logit transform to a float RangeParameter domain.

    Transform is done in-place.
    """

    def __init__(
        self,
        search_space: SearchSpace | None = None,
        observations: list[Observation] | None = None,
        adapter: Optional["adapter_module.base.Adapter"] = None,
        config: TConfig | None = None,
    ) -> None:
        assert search_space is not None, "Logit requires search space"
        # Identify parameters that should be transformed
        self.transform_parameters: set[str] = {
            p_name
            for p_name, p in search_space.parameters.items()
            if isinstance(p, RangeParameter)
            and p.parameter_type == ParameterType.FLOAT
            and p.logit_scale is True
        }

    def transform_observation_features(
        self, observation_features: list[ObservationFeatures]
    ) -> list[ObservationFeatures]:
        for obsf in observation_features:
            for p_name in self.transform_parameters:
                if p_name in obsf.parameters:
                    param: float = obsf.parameters[p_name]  # pyre-ignore [9]
                    obsf.parameters[p_name] = logit(param).item()
        return observation_features

    def _transform_search_space(self, search_space: SearchSpace) -> SearchSpace:
        for p_name, p in search_space.parameters.items():
            if p_name in self.transform_parameters and isinstance(p, RangeParameter):
                p.set_logit_scale(False).update_range(
                    lower=logit(p.lower).item(), upper=logit(p.upper).item()
                )
                if p.target_value is not None:
                    p._target_value = logit(p.target_value).item()
        return search_space

    def untransform_observation_features(
        self, observation_features: list[ObservationFeatures]
    ) -> list[ObservationFeatures]:
        for obsf in observation_features:
            for p_name in self.transform_parameters:
                if p_name in obsf.parameters:
                    param: float = obsf.parameters[p_name]  # pyre-ignore [9]
                    obsf.parameters[p_name] = expit(param).item()
        return observation_features
