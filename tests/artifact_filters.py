#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the helper for filtering based on artifact definitions."""

import unittest

from artifacts import reader as artifacts_reader
from artifacts import registry as artifacts_registry

from dfimagetools import artifact_filters
from dfimagetools import resources

from tests import test_lib


class ArtifactDefinitionFiltersGeneratorTest(test_lib.BaseTestCase):
  """Tests for the artifact definition filters generator."""

  # pylint: disable=protected-access

  def testBuildFindSpecsFromArtifactDefinition(self):
    """Tests the GetFindSpecs function."""
    registry = artifacts_registry.ArtifactDefinitionsRegistry()
    reader = artifacts_reader.YamlArtifactsReader()

    test_artifacts_path = self._GetTestFilePath(['artifacts'])
    self._SkipIfPathNotExists(test_artifacts_path)

    registry.ReadFromDirectory(reader, test_artifacts_path)

    environment_variables = [resources.EnvironmentVariable(
        case_sensitive=False, name='%SystemRoot%', value='C:\\Windows')]

    # Test file artifact definition type.
    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, environment_variables, [])
    find_specs = list(test_generator._BuildFindSpecsFromArtifactDefinition(
        'TestFile2'))

    self.assertEqual(len(find_specs), 1)

    # Location segments should be equivalent to \Windows\test_data\*.evtx.
    # Underscores are not escaped in regular expressions in supported versions
    # of Python 3. See https://bugs.python.org/issue2650.
    expected_location_segments = ['Windows', 'test_data', '.*\\.evtx']

    self.assertEqual(
        find_specs[0]._location_segments, expected_location_segments)

    # Test group artifact definition type.
    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, environment_variables, [])
    find_specs = list(test_generator._BuildFindSpecsFromArtifactDefinition(
        'TestGroup1'))

    self.assertEqual(len(find_specs), 4)

  def testBuildFindSpecsFromFileSourcePath(self):
    """Tests the _BuildFindSpecsFromFileSourcePath function."""
    registry = artifacts_registry.ArtifactDefinitionsRegistry()
    reader = artifacts_reader.YamlArtifactsReader()

    test_artifacts_path = self._GetTestFilePath(['artifacts'])
    self._SkipIfPathNotExists(test_artifacts_path)

    registry.ReadFromDirectory(reader, test_artifacts_path)

    # Test expansion of environment variables.
    environment_variables = [resources.EnvironmentVariable(
        case_sensitive=False, name='%SystemRoot%', value='C:\\Windows')]

    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, environment_variables, [])
    find_specs = list(test_generator._BuildFindSpecsFromFileSourcePath(
        '%%environ_systemroot%%\\test_data\\*.evtx', '\\'))

    self.assertEqual(len(find_specs), 1)

    # Location segments should be equivalent to \Windows\test_data\*.evtx.
    # Underscores are not escaped in regular expressions in supported versions
    # of Python 3. See https://bugs.python.org/issue2650.
    expected_location_segments = ['Windows', 'test_data', '.*\\.evtx']

    self.assertEqual(
        find_specs[0]._location_segments, expected_location_segments)

    # Test expansion of globs.
    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, [], [])
    find_specs = list(test_generator._BuildFindSpecsFromFileSourcePath(
        '\\test_data\\**', '\\'))

    # Glob expansion should by default recurse ten levels.
    self.assertEqual(len(find_specs), 10)

    # Last entry in find_specs list should be 10 levels of depth.
    # Underscores are not escaped in regular expressions in supported versions
    # of Python 3. See https://bugs.python.org/issue2650
    expected_location_segments = ['test_data']

    expected_location_segments.extend([
        '.*', '.*', '.*', '.*', '.*', '.*', '.*', '.*', '.*', '.*'])

    self.assertEqual(
        find_specs[9]._location_segments, expected_location_segments)

    # Test expansion of user home directories
    test_user1 = resources.UserAccount(
        user_directory='/homes/testuser1', username='testuser1')
    test_user2 = resources.UserAccount(
        user_directory='/home/testuser2', username='testuser2')

    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, [], [test_user1, test_user2])
    find_specs = list(test_generator._BuildFindSpecsFromFileSourcePath(
        '%%users.homedir%%/.thumbnails/**3', '/'))

    # 6 find specs should be created for testuser1 and testuser2.
    self.assertEqual(len(find_specs), 6)

    # Last entry in find_specs list should be testuser2 with a depth of 3
    expected_location_segments = [
        'home', 'testuser2', '\\.thumbnails', '.*', '.*', '.*']
    self.assertEqual(
        find_specs[5]._location_segments, expected_location_segments)

    # Test Windows path with profile directories and globs with a depth of 4.
    test_user1 = resources.UserAccount(
        user_directory='C:\\Users\\testuser1',
        user_directory_path_separator='\\', username='testuser1')
    test_user2 = resources.UserAccount(
        user_directory='%SystemDrive%\\Users\\testuser2',
        user_directory_path_separator='\\', username='testuser2')

    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, [], [test_user1, test_user2])
    find_specs = list(test_generator._BuildFindSpecsFromFileSourcePath(
        '%%users.userprofile%%\\AppData\\**4', '\\'))

    # 8 find specs should be created for testuser1 and testuser2.
    self.assertEqual(len(find_specs), 8)

    # Last entry in find_specs list should be testuser2, with a depth of 4.
    expected_location_segments = [
        'Users', 'testuser2', 'AppData', '.*', '.*', '.*', '.*']
    self.assertEqual(
        find_specs[7]._location_segments, expected_location_segments)

    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, [], [test_user1, test_user2])
    find_specs = list(test_generator._BuildFindSpecsFromFileSourcePath(
        '%%users.localappdata%%\\Microsoft\\**4', '\\'))

    # 16 find specs should be created for testuser1 and testuser2.
    self.assertEqual(len(find_specs), 16)

    # Last entry in find_specs list should be testuser2, with a depth of 4.
    expected_location_segments = [
        'Users', 'testuser2', 'Local\\ Settings', 'Application\\ Data',
        'Microsoft', '.*', '.*', '.*', '.*']
    self.assertEqual(
        find_specs[15]._location_segments, expected_location_segments)

  def testGetFindSpecs(self):
    """Tests the GetFindSpecs function."""
    registry = artifacts_registry.ArtifactDefinitionsRegistry()
    reader = artifacts_reader.YamlArtifactsReader()

    test_artifacts_path = self._GetTestFilePath(['artifacts'])
    self._SkipIfPathNotExists(test_artifacts_path)

    registry.ReadFromDirectory(reader, test_artifacts_path)

    environment_variables = [resources.EnvironmentVariable(
        case_sensitive=False, name='%SystemRoot%', value='C:\\Windows')]

    test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
        registry, environment_variables, [])
    find_specs = list(test_generator.GetFindSpecs(['TestFile2']))

    self.assertEqual(len(find_specs), 1)

    # Location segments should be equivalent to \Windows\test_data\*.evtx.
    # Underscores are not escaped in regular expressions in supported versions
    # of Python 3. See https://bugs.python.org/issue2650.
    expected_location_segments = ['Windows', 'test_data', '.*\\.evtx']

    self.assertEqual(
        find_specs[0]._location_segments, expected_location_segments)


if __name__ == '__main__':
  unittest.main()
