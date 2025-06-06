#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from collections.abc import Sequence
from typing import Any

from ax.core.search_space import SearchSpaceDigest
from ax.core.types import TCandidateMetadata
from ax.models.torch.botorch import LegacyBoTorchGenerator
from ax.models.torch_base import TorchGenerator
from ax.utils.common.docutils import copy_doc
from botorch.fit import fit_gpytorch_mll
from botorch.models.contextual import SACGP
from botorch.models.gpytorch import GPyTorchModel
from botorch.models.model_list_gp_regression import ModelListGP
from botorch.utils.datasets import SupervisedDataset
from gpytorch.mlls.exact_marginal_log_likelihood import ExactMarginalLogLikelihood
from torch import Tensor


MIN_OBSERVED_NOISE_LEVEL = 1e-7


class SACBO(LegacyBoTorchGenerator):
    """Does Bayesian optimization with structural additive contextual GP (SACGP).
    The parameter space decomposition must be provided.

    Args:
        decomposition: Keys are context names. Values are the lists of parameter
            names belong to the context, e.g.
            {'context1': ['p1_c1', 'p2_c1'],'context2': ['p1_c2', 'p2_c2']}.
    """

    def __init__(self, decomposition: dict[str, list[str]]) -> None:
        # add validation for input decomposition
        for param_list in decomposition.values():
            assert len(param_list) == len(
                list(decomposition.values())[0]
            ), "Each Context must contain same number of parameters"
        self.decomposition = decomposition
        self.feature_names: list[str] = []
        super().__init__(model_constructor=self.get_and_fit_model)

    @copy_doc(TorchGenerator.fit)
    def fit(
        self,
        datasets: Sequence[SupervisedDataset],
        search_space_digest: SearchSpaceDigest,
        candidate_metadata: list[list[TCandidateMetadata]] | None = None,
    ) -> None:
        if len(search_space_digest.feature_names) == 0:
            raise ValueError("feature names are required for SACBO")
        self.feature_names = search_space_digest.feature_names
        super().fit(
            datasets=datasets,
            search_space_digest=search_space_digest,
        )

    def get_and_fit_model(
        self,
        Xs: list[Tensor],
        Ys: list[Tensor],
        Yvars: list[Tensor],
        task_features: list[int],
        fidelity_features: list[int],
        metric_names: list[str],
        state_dict: dict[str, Tensor] | None = None,
        fidelity_model_id: int | None = None,
        **kwargs: Any,
    ) -> GPyTorchModel:
        """Get a fitted StructuralAdditiveContextualGP model for each outcome.
        Args:
            Xs: X for each outcome.
            Ys: Y for each outcome.
            Yvars: Noise variance of Y for each outcome.
        Returns: Fitted StructuralAdditiveContextualGP model.
        """
        # generate model space decomposition dict
        decomp_index = generate_model_space_decomposition(
            decomposition=self.decomposition, feature_names=self.feature_names
        )

        models = []
        for i, X in enumerate(Xs):
            Yvar = Yvars[i].clamp_min_(MIN_OBSERVED_NOISE_LEVEL)
            gp_m = SACGP(X, Ys[i], Yvar, decomp_index)
            mll = ExactMarginalLogLikelihood(gp_m.likelihood, gp_m)
            fit_gpytorch_mll(mll)
            models.append(gp_m)

        if len(models) == 1:
            model = models[0]
        else:
            model = ModelListGP(*models)
        model.to(Xs[0])
        return model


def generate_model_space_decomposition(
    decomposition: dict[str, list[str]], feature_names: list[str]
) -> dict[str, list[int]]:
    # validate input decomposition
    for param_list in decomposition.values():
        for param in param_list:
            assert (
                param in feature_names
            ), f"cannot find parameter {param} in search space"

    # generate parameter index list align with the input arrays
    decomp_index = {}
    for context, param_names in decomposition.items():
        decomp_index[context] = [feature_names.index(p) for p in param_names]
    return decomp_index
