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

pytest_plugins = str('pytester')


TESTSUITE = """
from hypothesis import given
from hypothesis.strategies import integers
import pytest

@given(integers())
def test_to_be_skipped(x):
    if x == 0:
        pytest.skip("Don't run this test")
    else:
        assert x == 0

"""


def test_no_falsifying_example(testdir):
    script = testdir.makepyfile(TESTSUITE)
    result = testdir.runpytest(script, '--verbose')
    out = '\n'.join(result.stdout.lines)
    assert 'test_no_falsifying_example.py::test_to_be_skipped SKIPPED' in out
    assert 'Falsifying example' not in out
    assert result.ret == 0
