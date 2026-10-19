#!/usr/bin/env python3
"""Tests for the helper for filtering based on artifact definitions."""

import logging
import unittest

from artifacts import artifact as artifacts_artifact
from artifacts import definitions as artifacts_definitions
from artifacts import reader as artifacts_reader
from artifacts import registry as artifacts_registry

from dfimagetools import artifact_filters
from dfimagetools import resources

from tests import test_lib


class _FailingFindSpecGenerator(artifact_filters.ArtifactDefinitionFiltersGenerator):
    """Generator whose find specification building fails.

    A test double of ArtifactDefinitionFiltersGenerator that simulates
    an unable to build find specification instead of using the real
    dfVFS find specification builder.
    """

    # pylint: disable=invalid-overridden-method

    def _BuildFindSpec(self, location_glob, location_separator):
        """Builds a find specification for a location glob.

        Args:
          location_glob (str): location glob, unused.
          location_separator (str): location segment separator, unused.

        Raises:
          ValueError: always, simulating an unable to build find specification.
        """
        raise ValueError("Test find specification build error")


class ArtifactDefinitionFiltersGeneratorTest(test_lib.BaseTestCase):
    """Tests for the artifact definition filters generator."""

    # pylint: disable=protected-access

    def testBuildFindSpecsFromArtifactDefinition(self):
        """Tests the _BuildFindSpecsFromArtifactDefinition function."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()
        reader = artifacts_reader.YamlArtifactsReader()

        test_artifacts_path = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(test_artifacts_path)

        registry.ReadFromDirectory(reader, test_artifacts_path)

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        environment_variables = [
            resources.EnvironmentVariable(
                case_sensitive=False, name="%SystemRoot%", value="C:\\Windows"
            )
        ]
        # Test file artifact definition type.
        find_specs = list(
            test_generator._BuildFindSpecsFromArtifactDefinition(
                "TestFile2", environment_variables=environment_variables
            )
        )
        self.assertEqual(len(find_specs), 1)

        # Location segments should be equivalent to \Windows\test_data\*.evtx.
        # Underscores are not escaped in regular expressions in supported versions
        # of Python 3. See https://bugs.python.org/issue2650.
        expected_location_segments = ["Windows", "test_data", ".*\\.evtx"]

        self.assertEqual(find_specs[0]._location_segments, expected_location_segments)

        # Test group artifact definition type.
        find_specs = list(
            test_generator._BuildFindSpecsFromArtifactDefinition(
                "TestGroup1", environment_variables=environment_variables
            )
        )
        self.assertEqual(len(find_specs), 4)

    def testBuildFindSpecsFromArtifactDefinitionByAlias(self):
        """Tests the _BuildFindSpecsFromArtifactDefinition function by alias."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()

        definition = artifacts_artifact.ArtifactDefinition(
            name="TestFileWithAlias",
            aliases=["TestFileAlias"],
            description="Test file artifact definition",
        )
        definition.AppendSource(
            artifacts_definitions.TYPE_INDICATOR_FILE,
            {"paths": ["\\test_data\\*.evtx"], "separator": "\\"},
        )
        registry.RegisterDefinition(definition)

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        # The definition is not resolved by its name but by its alias.
        find_specs = list(
            test_generator._BuildFindSpecsFromArtifactDefinition("TestFileAlias")
        )
        self.assertEqual(len(find_specs), 1)

        # Location segments should be equivalent to \test_data\*.evtx.
        expected_location_segments = ["test_data", ".*\\.evtx"]
        self.assertEqual(find_specs[0]._location_segments, expected_location_segments)

    def testBuildFindSpecsFromUndefinedArtifactDefinition(self):
        """Tests _BuildFindSpecsFromArtifactDefinition with an undefined name."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        with self.assertLogs(level=logging.WARNING) as log_capture:
            find_specs = list(
                test_generator._BuildFindSpecsFromArtifactDefinition("TestUndefined")
            )

        self.assertEqual(len(find_specs), 0)
        self.assertIn(
            "WARNING:root:Undefined artifact definition: TestUndefined",
            log_capture.output,
        )

    def testBuildFindSpecsFromArtifactDefinitionWithUnsupportedSource(self):
        """Tests _BuildFindSpecsFromArtifactDefinition with an unsupported source."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()

        definition = artifacts_artifact.ArtifactDefinition(
            name="TestUnsupportedSource",
            description="Test artifact definition",
        )
        definition.AppendSource(
            artifacts_definitions.TYPE_INDICATOR_COMMAND,
            {"cmd": "test_command", "args": ["--test"]},
        )
        definition.AppendSource(
            artifacts_definitions.TYPE_INDICATOR_FILE,
            {"paths": ["\\test_data\\*.evtx"], "separator": "\\"},
        )
        registry.RegisterDefinition(definition)

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        find_specs = list(
            test_generator._BuildFindSpecsFromArtifactDefinition(
                "TestUnsupportedSource"
            )
        )
        # Only the file source should generate a find specification since the
        # command source is not supported by the filters generator.
        self.assertEqual(len(find_specs), 1)

    def testBuildFindSpecsFromArtifactDefinitionWithDirectorySource(self):
        """Tests _BuildFindSpecsFromArtifactDefinition with a directory source."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()

        definition = artifacts_artifact.ArtifactDefinition(
            name="TestDirectorySource",
            description="Test artifact definition",
        )
        definition.AppendSource(
            artifacts_definitions.TYPE_INDICATOR_DIRECTORY,
            {"paths": ["\\test_data"], "separator": "\\"},
        )
        registry.RegisterDefinition(definition)

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        with self.assertLogs(level=logging.WARNING) as log_capture:
            find_specs = list(
                test_generator._BuildFindSpecsFromArtifactDefinition(
                    "TestDirectorySource"
                )
            )

        # The deprecated directory source is not skipped but generates a find
        # specification.
        self.assertEqual(len(find_specs), 1)
        self.assertIn(
            (
                "WARNING:root:Use of deprecated source type: directory in artifact "
                "definition: TestDirectorySource"
            ),
            log_capture.output,
        )

    def testBuildFindSpecsFromFileSourcePath(self):
        """Tests the _BuildFindSpecsFromFileSourcePath function."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()
        reader = artifacts_reader.YamlArtifactsReader()

        test_artifacts_path = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(test_artifacts_path)

        registry.ReadFromDirectory(reader, test_artifacts_path)

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        environment_variables = [
            resources.EnvironmentVariable(
                case_sensitive=False, name="%SystemRoot%", value="C:\\Windows"
            )
        ]

        # Test expansion of environment variables.
        find_specs = list(
            test_generator._BuildFindSpecsFromFileSourcePath(
                "%%environ_systemroot%%\\test_data\\*.evtx",
                "\\",
                environment_variables=environment_variables,
            )
        )
        self.assertEqual(len(find_specs), 1)

        # Location segments should be equivalent to \Windows\test_data\*.evtx.
        # Underscores are not escaped in regular expressions in supported versions
        # of Python 3. See https://bugs.python.org/issue2650.
        expected_location_segments = ["Windows", "test_data", ".*\\.evtx"]

        self.assertEqual(find_specs[0]._location_segments, expected_location_segments)

        # Test expansion of globs.
        find_specs = list(
            test_generator._BuildFindSpecsFromFileSourcePath("\\test_data\\**", "\\")
        )
        # Glob expansion should by default recurse ten levels.
        self.assertEqual(len(find_specs), 10)

        # Last entry in find_specs list should be 10 levels of depth.
        # Underscores are not escaped in regular expressions in supported versions
        # of Python 3. See https://bugs.python.org/issue2650
        expected_location_segments = ["test_data"]

        expected_location_segments.extend(
            [".*", ".*", ".*", ".*", ".*", ".*", ".*", ".*", ".*", ".*"]
        )
        self.assertEqual(find_specs[9]._location_segments, expected_location_segments)

        # Test expansion of user home directories
        test_user1 = resources.UserAccount(
            user_directory="/homes/testuser1", username="testuser1"
        )
        test_user2 = resources.UserAccount(
            user_directory="/home/testuser2", username="testuser2"
        )
        find_specs = list(
            test_generator._BuildFindSpecsFromFileSourcePath(
                "%%users.homedir%%/.thumbnails/**3",
                "/",
                user_accounts=[test_user1, test_user2],
            )
        )
        # 6 find specs should be created for testuser1 and testuser2.
        self.assertEqual(len(find_specs), 6)

        # Last entry in find_specs list should be testuser2 with a depth of 3
        expected_location_segments = [
            "home",
            "testuser2",
            "\\.thumbnails",
            ".*",
            ".*",
            ".*",
        ]
        self.assertEqual(find_specs[5]._location_segments, expected_location_segments)

        # Test Windows path with profile directories and globs with a depth of 4.
        test_user1 = resources.UserAccount(
            user_directory="C:\\Users\\testuser1",
            user_directory_path_separator="\\",
            username="testuser1",
        )
        test_user2 = resources.UserAccount(
            user_directory="%SystemDrive%\\Users\\testuser2",
            user_directory_path_separator="\\",
            username="testuser2",
        )
        find_specs = list(
            test_generator._BuildFindSpecsFromFileSourcePath(
                "%%users.userprofile%%\\AppData\\**4",
                "\\",
                user_accounts=[test_user1, test_user2],
            )
        )
        # 8 find specs should be created for testuser1 and testuser2.
        self.assertEqual(len(find_specs), 8)

        # Last entry in find_specs list should be testuser2, with a depth of 4.
        expected_location_segments = [
            "Users",
            "testuser2",
            "AppData",
            ".*",
            ".*",
            ".*",
            ".*",
        ]
        self.assertEqual(find_specs[7]._location_segments, expected_location_segments)

        find_specs = list(
            test_generator._BuildFindSpecsFromFileSourcePath(
                "%%users.localappdata%%\\Microsoft\\**4",
                "\\",
                user_accounts=[test_user1, test_user2],
            )
        )
        # 16 find specs should be created for testuser1 and testuser2.
        self.assertEqual(len(find_specs), 16)

        # Last entry in find_specs list should be testuser2, with a depth of 4.
        expected_location_segments = [
            "Users",
            "testuser2",
            "Local\\ Settings",
            "Application\\ Data",
            "Microsoft",
            ".*",
            ".*",
            ".*",
            ".*",
        ]
        self.assertEqual(find_specs[15]._location_segments, expected_location_segments)

    def testBuildFindSpecsFromFileSourcePathWithoutLeadingSeparator(self):
        """Tests _BuildFindSpecsFromFileSourcePath with a relative path."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        # A relative path is not used as a find specification.
        find_specs = list(
            test_generator._BuildFindSpecsFromFileSourcePath("test_data\\*.evtx", "\\")
        )
        self.assertEqual(len(find_specs), 0)

    def testBuildFindSpecsFromFileSourcePathWithBuildError(self):
        """Tests _BuildFindSpecsFromFileSourcePath when building fails."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()

        test_generator = _FailingFindSpecGenerator(registry)

        with self.assertLogs(level=logging.ERROR) as log_capture:
            find_specs = list(
                test_generator._BuildFindSpecsFromFileSourcePath(
                    "\\test_data\\*.evtx", "\\"
                )
            )

        self.assertEqual(len(find_specs), 0)
        self.assertIn(
            (
                "ERROR:root:Unable to build find specification for path: "
                '"\\test_data\\*.evtx" with error: '
                "Test find specification build error"
            ),
            log_capture.output,
        )

    def testGetFindSpecs(self):
        """Tests the GetFindSpecs function."""
        registry = artifacts_registry.ArtifactDefinitionsRegistry()
        reader = artifacts_reader.YamlArtifactsReader()

        test_artifacts_path = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(test_artifacts_path)

        registry.ReadFromDirectory(reader, test_artifacts_path)

        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

        environment_variables = [
            resources.EnvironmentVariable(
                case_sensitive=False, name="%SystemRoot%", value="C:\\Windows"
            )
        ]
        find_specs = list(
            test_generator.GetFindSpecs(
                names=["TestFile2"], environment_variables=environment_variables
            )
        )
        self.assertEqual(len(find_specs), 1)

        # Location segments should be equivalent to \Windows\test_data\*.evtx.
        # Underscores are not escaped in regular expressions in supported versions
        # of Python 3. See https://bugs.python.org/issue2650.
        expected_location_segments = ["Windows", "test_data", ".*\\.evtx"]

        self.assertEqual(find_specs[0]._location_segments, expected_location_segments)

    def testGetFindSpecsWithGeneratorArguments(self):
        """Tests the GetFindSpecs function using generator arguments.

        Passing environment variables and user accounts via the constructor is
        deprecated but still supported.
        """
        registry = artifacts_registry.ArtifactDefinitionsRegistry()
        reader = artifacts_reader.YamlArtifactsReader()

        test_artifacts_path = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(test_artifacts_path)

        registry.ReadFromDirectory(reader, test_artifacts_path)

        environment_variables = [
            resources.EnvironmentVariable(
                case_sensitive=False, name="%SystemRoot%", value="C:\\Windows"
            )
        ]
        test_user = resources.UserAccount(
            user_directory="/home/testuser", username="testuser"
        )
        test_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(
            registry,
            environment_variables=environment_variables,
            user_accounts=[test_user],
        )
        find_specs = list(test_generator.GetFindSpecs(names=["TestFile1", "TestFile2"]))

        self.assertEqual(len(find_specs), 2)

        # Location segments should be equivalent to /home/testuser/AUTHORS.
        find_spec = next(
            find_spec
            for find_spec in find_specs
            if find_spec._location_segments[0] == "home"
        )
        self.assertEqual(find_spec._location_segments, ["home", "testuser", "AUTHORS"])

        # Location segments should be equivalent to \Windows\test_data\*.evtx.
        find_spec = next(
            find_spec
            for find_spec in find_specs
            if find_spec._location_segments[0] == "Windows"
        )
        self.assertEqual(
            find_spec._location_segments, ["Windows", "test_data", ".*\\.evtx"]
        )


if __name__ == "__main__":
    unittest.main()
