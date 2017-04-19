# coding=utf-8
#
# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis-python
#
# Most of this work is copyright (C) 2013-2016 David R. MacIver
# (david@drmaciver.com), but it contains contributions by others. See
# CONTRIBUTING.rst for a full list of people who may hold copyright, and
# consult the git log if you need to determine who owns an individual
# contribution.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at http://mozilla.org/MPL/2.0/.
#
# END HEADER

from __future__ import division, print_function, absolute_import

import os
import sys
import unittest

import pytest

from hypothesis import given, reporting
from tests.common.utils import capture_err, capture_out
from hypothesis._settings import Verbosity, settings
from hypothesis.reporting import report, debug_report, verbose_report
from hypothesis.strategies import integers
from hypothesis.internal.compat import PY2


def test_no_falsifying_example_if_skip():

    class DemoTest(unittest.TestCase):

        @given(integers())
        def test_to_be_skipped(self, x):
            if x == 0:
                raise unittest.SkipTest()
            else:
                assert x == 0

    with capture_out() as o:
        with reporting.with_reporter(reporting.silent):
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(DemoTest)
            unittest.TextTestRunner().run(suite)

    print(o)
    assert False
    # assert u'Falsifying example' not in o.getvalue()
