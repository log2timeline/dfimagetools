#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the helper to list file entries."""

import unittest

from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.resolver import resolver
from dfvfs.path import factory as path_spec_factory

from dfimagetools import file_entry_lister

from tests import test_lib


class FileEntryListerTest(test_lib.BaseTestCase):
  """Tests for the file entry lister."""

  # pylint: disable=protected-access

  def testListFileEntry(self):
    """Tests the _ListFileEntry function."""
    path = self._GetTestFilePath(['image.qcow2'])
    self._SkipIfPathNotExists(path)

    test_lister = file_entry_lister.FileEntryLister()

    path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.TYPE_INDICATOR_OS, location=path)
    path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.TYPE_INDICATOR_QCOW, parent=path_spec)
    path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.TYPE_INDICATOR_TSK, location='/passwords.txt',
        parent=path_spec)

    file_system = resolver.Resolver.OpenFileSystem(path_spec)
    file_entry = resolver.Resolver.OpenFileEntry(path_spec)

    file_entries = list(test_lister._ListFileEntry(
        file_system, file_entry, ['']))

    self.assertEqual(len(file_entries), 1)

    expected_path_segments = [
        ['', 'passwords.txt']]

    path_segments = [segments for _, segments in file_entries]
    self.assertEqual(path_segments, expected_path_segments)

  def testGetBasePathSpecs(self):
    """Tests the GetBasePathSpecs function."""
    path = self._GetTestFilePath(['image.qcow2'])
    self._SkipIfPathNotExists(path)

    test_lister = file_entry_lister.FileEntryLister()

    expected_path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.TYPE_INDICATOR_OS, location=path)
    expected_path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.TYPE_INDICATOR_QCOW, parent=expected_path_spec)
    expected_path_spec = path_spec_factory.Factory.NewPathSpec(
        dfvfs_definitions.PREFERRED_EXT_BACK_END, location='/',
        parent=expected_path_spec)

    base_path_specs = test_lister.GetBasePathSpecs(path)
    self.assertEqual(base_path_specs, [expected_path_spec])

  def testListFileEntries(self):
    """Tests the ListFileEntries function."""
    path = self._GetTestFilePath(['image.qcow2'])
    self._SkipIfPathNotExists(path)

    test_lister = file_entry_lister.FileEntryLister()

    base_path_specs = test_lister.GetBasePathSpecs(path)
    file_entries = list(test_lister.ListFileEntries(base_path_specs))

    self.assertEqual(len(file_entries), 6)

    expected_path_segments = [
        [''],
        ['', 'lost+found'],
        ['', 'a_directory'],
        ['', 'a_directory', 'another_file'],
        ['', 'a_directory', 'a_file'],
        ['', 'passwords.txt']]

    if dfvfs_definitions.PREFERRED_EXT_BACK_END == (
        dfvfs_definitions.TYPE_INDICATOR_TSK):
      expected_path_segments.append(['', '$OrphanFiles'])

    path_segments = [segments for _, segments in file_entries]

    self.assertEqual(len(path_segments), len(expected_path_segments))
    self.assertEqual(path_segments, expected_path_segments)


if __name__ == '__main__':
  unittest.main()
