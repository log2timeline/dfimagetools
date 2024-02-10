#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the helper for filtering based on a path."""

import unittest

from dfimagetools import path_filters

from tests import test_lib


class PathFiltersGeneratorTest(test_lib.BaseTestCase):
  """Tests for the path filters generator."""

  # pylint: disable=protected-access

  def testGetFindSpecs(self):
    """Tests the GetFindSpecs function."""
    test_generator = path_filters.PathFiltersGenerator(
        '/test_directory1/test_file1.txt')

    self.assertIsNone(test_generator.partition)

    find_specs = list(test_generator.GetFindSpecs())

    self.assertEqual(len(find_specs), 1)

    expected_location_segments = ['test_directory1', 'test_file1.txt']

    self.assertEqual(
        find_specs[0]._location_segments, expected_location_segments)

    test_generator = path_filters.PathFiltersGenerator(
        '/p2/test_directory1/test_file1.txt')

    self.assertEqual(test_generator.partition, 'p2')

    find_specs = list(test_generator.GetFindSpecs())

    self.assertEqual(len(find_specs), 1)

    expected_location_segments = ['test_directory1', 'test_file1.txt']

    self.assertEqual(
        find_specs[0]._location_segments, expected_location_segments)


if __name__ == '__main__':
  unittest.main()
