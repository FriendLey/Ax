#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from numbers import Real
from typing import cast, Optional, TYPE_CHECKING

from ax.adapter.transforms.base import Transform
from ax.adapter.transforms.utils import construct_new_search_space

from ax.core.observation import Observation
from ax.core.parameter import ChoiceParameter, Parameter, ParameterType, RangeParameter
from ax.core.search_space import SearchSpace
from ax.models.types import TConfig

if TYPE_CHECKING:
    # import as module to make sphinx-autodoc-typehints happy
    from ax import adapter as adapter_module  # noqa F401


class IntRangeToChoice(Transform):
    """Convert a RangeParameter of type int to a ordered ChoiceParameter.

    Transform is done in-place.
    """

    def __init__(
        self,
        search_space: SearchSpace | None = None,
        observations: list[Observation] | None = None,
        adapter: Optional["adapter_module.base.Adapter"] = None,
        config: TConfig | None = None,
    ) -> None:
        assert search_space is not None, "IntRangeToChoice requires search space"
        config = config or {}
        self.max_choices: float = float(
            cast(Real, (config.get("max_choices", float("inf"))))
        )
        # Identify parameters that should be transformed
        self.transform_parameters: set[str] = {
            p_name
            for p_name, p in search_space.parameters.items()
            if isinstance(p, RangeParameter)
            and p.parameter_type == ParameterType.INT
            and p.cardinality() <= self.max_choices
        }

    def _transform_search_space(self, search_space: SearchSpace) -> SearchSpace:
        transformed_parameters: dict[str, Parameter] = {}
        for p_name, p in search_space.parameters.items():
            if (
                p_name in self.transform_parameters
                and isinstance(p, RangeParameter)
                and p.parameter_type == ParameterType.INT
                and p.cardinality() <= self.max_choices
            ):
                values = list(range(int(p.lower), int(p.upper) + 1))
                target_value = (
                    None
                    if p.target_value is None
                    else next(i for i, v in enumerate(values) if v == p.target_value)
                )
                transformed_parameters[p_name] = ChoiceParameter(
                    name=p_name,
                    parameter_type=p.parameter_type,
                    values=values,  # pyre-fixme[6]
                    is_ordered=True,
                    is_fidelity=p.is_fidelity,
                    target_value=target_value,
                )
            else:
                transformed_parameters[p.name] = p
        return construct_new_search_space(
            search_space=search_space,
            parameters=list(transformed_parameters.values()),
            parameter_constraints=[
                pc.clone_with_transformed_parameters(
                    transformed_parameters=transformed_parameters
                )
                for pc in search_space.parameter_constraints
            ],
        )
