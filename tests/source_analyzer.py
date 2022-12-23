#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the helper to volumes and file systems in a storage media image."""

import unittest

from dfimagetools import source_analyzer

from tests import test_lib


class SourceAnalyzerTest(test_lib.BaseTestCase):
  """Tests for the source analyzer."""

  def testAnalyze(self):
    """Tests the Analyze function."""
    path = self._GetTestFilePath(['image.qcow2'])
    self._SkipIfPathNotExists(path)

    test_analyzer = source_analyzer.SourceAnalyzer()
    source_context = list(test_analyzer.Analyze(path))[0]

    self.assertIsNotNone(source_context)


if __name__ == '__main__':
  unittest.main()
