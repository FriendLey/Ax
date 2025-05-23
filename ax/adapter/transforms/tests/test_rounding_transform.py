#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import numpy as np
from ax.adapter.transforms.rounding import randomized_onehot_round, strict_onehot_round
from ax.utils.common.testutils import TestCase


class RoundingTest(TestCase):
    def test_OneHotRound(self) -> None:
        self.assertTrue(
            np.allclose(
                strict_onehot_round(np.array([0.1, 0.5, 0.3])), np.array([0, 1, 0])
            )
        )
        # One item should be set to one at random.
        self.assertEqual(
            np.count_nonzero(
                np.isclose(
                    randomized_onehot_round(np.array([0.0, 0.0, 0.0])),
                    np.array([1, 1, 1]),
                )
            ),
            1,
        )
        # Negative value is not selected.
        self.assertEqual(randomized_onehot_round(np.array([0.0, -1.0, 0.0]))[1], 0.0)
