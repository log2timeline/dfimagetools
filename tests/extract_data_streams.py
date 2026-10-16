#!/usr/bin/env python3
"""Tests for the console script to extract data streams.

The tests exercise the console script in a subprocess so it is tested as a
real command line program: the arguments, the working directory, the streams
and the exit code are all the real ones and no mocking of the process
environment is required.

Error conditions that are normally simulated are instead reproduced with real
inputs:
  * an unreadable source file makes the scanner fail with a scanner error,
  * a GPT image without valid partitions generates no base path
    specifications,
  * a GPT image with multiple partitions leads to an interactive prompt at
    which the script is aborted by a signal,
  * a symbolic link within the target path that points outside of the
    target path makes the sanitized destination path escape the target
    path,
  * a read-only destination directory makes the write of the destination
    file fail.

The GPT images are stored as static test data files in the test data
directory instead of being generated at runtime.
"""

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import unittest

from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import file_entry_lister
from tests import test_lib


class ExtractDataStreamsTest(test_lib.BaseTestCase):
    """Tests for the extract data streams console script."""

    # The path to the console script under test relative to the project root.
    _SCRIPT_PATH = os.path.join("dfimagetools", "scripts", "extract_data_streams.py")

    def _GetSubprocessEnvironment(self, extra_pythonpath=None):
        """Creates the environment for a subprocess of the console script.

        Args:
          extra_pythonpath (Optional[str]): additional path to prepend to the
              PYTHONPATH variable, e.g. to shadow a package.

        Returns:
          dict[str, str]: the environment of the subprocess.
        """
        pythonpath_parts = []
        if extra_pythonpath:
            pythonpath_parts.append(extra_pythonpath)
        pythonpath_parts.append(test_lib.PROJECT_PATH)
        if os.environ.get("PYTHONPATH"):
            pythonpath_parts.append(os.environ["PYTHONPATH"])

        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

        # Note that the console script writes prompts to stdout without
        # explicitly flushing them, so the output is made unbuffered to make
        # sure they are visible to the tests.
        environment["PYTHONUNBUFFERED"] = "1"

        return environment

    def _RunScript(self, argv, cwd=None, extra_pythonpath=None, timeout=300):
        """Runs the console script in a subprocess with the provided arguments.

        Args:
          argv (list[str]): command line arguments to pass to the script.
          cwd (Optional[str]): working directory of the subprocess.
          extra_pythonpath (Optional[str]): additional path to prepend to the
              PYTHONPATH variable of the subprocess, e.g. to shadow a package.
          timeout (int): number of seconds before the subprocess times out.

        Returns:
          subprocess.CompletedProcess: result of running the subprocess.
        """
        script_path = os.path.join(test_lib.PROJECT_PATH, self._SCRIPT_PATH)

        return subprocess.run(
            [sys.executable, script_path, *argv],
            check=False,
            cwd=cwd,
            env=self._GetSubprocessEnvironment(extra_pythonpath),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def _SkipIfGPTScenarioNotReproducible(self, image_path, num_partitions):
        """Skips the test when the GPT scenario cannot be reproduced.

        The GPT images are static test data files. Depending on the versions
        of the underlying libraries, not all environments are able to scan a
        GPT image with the expected result. The test is skipped rather than
        failing when the environment does not scan the image as expected:
          * an image with multiple partitions raises a scanner error since no
            mediator is provided for the interactive prompt,
          * an image without partitions generates no base path specifications.

        Args:
          image_path (str): path of the GPT image.
          num_partitions (int): number of valid partition entries in the image.

        Raises:
          SkipTest: when the image cannot be scanned as expected.
        """
        lister = file_entry_lister.FileEntryLister()

        try:
            base_path_specs = lister.GetBasePathSpecs(image_path)
        except dfvfs_errors.ScannerError:
            if num_partitions == 2:
                return

            self.skipTest("GPT image was not scanned as expected")

        except Exception as exception:  # pylint: disable=broad-except
            self.skipTest(f"unable to scan a GPT image: {exception!s}")

        if not (num_partitions == 0 and not base_path_specs):
            self.skipTest("GPT image was not scanned as expected")

    def testMainNoSource(self):
        """Tests main without a source image."""
        result = self._RunScript([])
        self.assertEqual(1, result.returncode)
        self.assertIn("Source value is missing.", result.stdout)

    def testMainNoExtractionFilters(self):
        """Tests main without any extraction filters."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        result = self._RunScript([ntfs_image_path])
        self.assertEqual(1, result.returncode)
        self.assertIn("[ERROR] no extraction filters were specified.", result.stdout)

    def testMainArtifactFiltersWithoutDefinitions(self):
        """Tests main when artifact filters are specified without definitions.

        The artifacts package is shadowed with a stub package that contains
        no data files so that the default artifact definitions path does not
        exist. This cannot be tested on systems that provide artifact
        definitions in /usr/share/artifacts since the script falls back to
        that path.
        """
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        if os.path.exists("/usr/share/artifacts"):
            self.skipTest("system artifact definitions exist at /usr/share/artifacts")

        with (
            test_lib.TempDirectory() as stub_dir,
            test_lib.TempDirectory() as temp_dir,
        ):
            stub_package_path = os.path.join(stub_dir, "artifacts")
            os.makedirs(stub_package_path)
            for module in ("__init__", "definitions", "reader", "registry"):
                # The modules only need to exist for the imports of the
                # script to succeed.
                stub_module_path = os.path.join(stub_package_path, f"{module}.py")
                with open(stub_module_path, "w", encoding="utf-8"):
                    pass

            target_path = os.path.join(temp_dir, "target")
            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ],
                extra_pythonpath=stub_dir,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "[ERROR] artifact filters were specified but no paths to artifact "
            "definitions were provided.",
            result.stdout,
        )

    def testMainArtifactFilterWithoutFindSpecs(self):
        """Tests main when an artifact filter generates no find specifications.

        An artifact filter that does not correspond to any known artifact
        definition generates no find specifications.
        """
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "UndefinedArtifactName",
                    "--artifact_definitions",
                    artifact_definitions,
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "[ERROR] an extraction filter was specified but no "
            "corresponding find specifications were generated.",
            result.stdout,
        )

    def testMainTargetNotADirectory(self):
        """Tests main when the target path is a file instead of a directory."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")
            with open(target_path, "w", encoding="utf-8") as file_object:
                file_object.write("test")

            result = self._RunScript(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("[ERROR] target path is not a directory.", result.stdout)

    def testMainUnsupportedTimeFilter(self):
        """Tests main with unsupported time filters."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            for time_filter in ("mtime,bad", "mtime,2019-13-45,2020-01-01"):
                result = self._RunScript(
                    [
                        "--time_filter",
                        time_filter,
                        "-t",
                        target_path,
                        ntfs_image_path,
                    ]
                )
                self.assertEqual(1, result.returncode)
                self.assertIn("[ERROR] unsupported time filter:", result.stdout)

    def testMainExtractSingleFile(self):
        """Tests main when extracting a single file using a path filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )
            self.assertIn(f"Writing hashes.json to: {target_path:s}", result.stderr)

            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

            with open(extracted_path, "rb") as file_object:
                digest = hashlib.sha256(file_object.read()).hexdigest()

            hashes_file_path = os.path.join(target_path, "hashes.json")
            self.assertTrue(os.path.exists(hashes_file_path))
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual(digest, hashes[0]["sha256"])
            self.assertEqual(
                [os.path.join("p1", "testdir2", "TestFile1")],
                hashes[0]["paths"],
            )

    def testMainExtractSingleFileWithoutPartition(self):
        """Tests main when extracting a file using a partitionless path."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--path",
                    "/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )
            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

    def testMainExtractPathFilterOverridePartitions(self):
        """Tests main when a path filter overrides the --partitions option."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "--partitions",
                    "2",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "[WARNING] partition specified in path filter will override "
                "--partitions command line argument.",
                result.stdout,
            )
            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

    def testMainExtractArtifactDefinitions(self):
        """Tests main when extracting files using artifact definitions."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    "--artifact_definitions",
                    artifact_definitions,
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )
            for path_segments in (
                ["p1", "testdir2", "TestFile1"],
                ["p1", "testdir2", "testfile1"],
            ):
                extracted_path = os.path.join(target_path, *path_segments)
                self.assertTrue(os.path.isfile(extracted_path))

            hashes_file_path = os.path.join(target_path, "hashes.json")
            self.assertTrue(os.path.exists(hashes_file_path))
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(2, len(hashes))
            # On the case-insensitive NTFS volume both file paths in the
            # definition match both files in the image, so each data stream
            # is hashed twice.
            test_file1 = os.path.join("p1", "testdir2", "TestFile1")
            test_file2 = os.path.join("p1", "testdir2", "testfile1")
            hash_paths = sorted(path for hash in hashes for path in hash["paths"])
            self.assertEqual(
                [test_file1, test_file1, test_file2, test_file2],
                hash_paths,
            )
            self.assertNotEqual(hashes[0]["sha256"], hashes[1]["sha256"])

    def testMainExtractArtifactDefinitionFile(self):
        """Tests main when artifact definitions are read from a single file."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(
            ["artifacts", "artifacts_ntfs.yaml"]
        )
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    "--artifact_definitions",
                    artifact_definitions,
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )
            for path_segments in (
                ["p1", "testdir2", "TestFile1"],
                ["p1", "testdir2", "testfile1"],
            ):
                extracted_path = os.path.join(target_path, *path_segments)
                self.assertTrue(os.path.isfile(extracted_path))

    def testMainExtractCustomArtifactDefinitions(self):
        """Tests main when custom artifact definitions are read from a directory."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    "--custom_artifact_definitions",
                    artifact_definitions,
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )
            for path_segments in (
                ["p1", "testdir2", "TestFile1"],
                ["p1", "testdir2", "testfile1"],
            ):
                extracted_path = os.path.join(target_path, *path_segments)
                self.assertTrue(os.path.isfile(extracted_path))

    def testMainExtractCustomArtifactDefinitionFile(self):
        """Tests main when custom artifact definitions are read from a file."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(
            ["artifacts", "artifacts_ntfs.yaml"]
        )
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    "--custom_artifact_definitions",
                    artifact_definitions,
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )
            for path_segments in (
                ["p1", "testdir2", "TestFile1"],
                ["p1", "testdir2", "testfile1"],
            ):
                extracted_path = os.path.join(target_path, *path_segments)
                self.assertTrue(os.path.isfile(extracted_path))

    def testMainExtractSkipsDuplicateDataStreams(self):
        """Tests main when duplicate data streams are skipped."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsHardlinks",
                    "--artifact_definitions",
                    artifact_definitions,
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("Extracting: /p1/file_hardlink1 to:", result.stderr)
            self.assertIn("skipped: duplicate of", result.stderr)

            extracted_path = os.path.join(target_path, "p1", "file_hardlink1")
            self.assertTrue(os.path.isfile(extracted_path))
            duplicate_path = os.path.join(target_path, "p1", "testdir1", "testfile1")
            self.assertFalse(os.path.exists(duplicate_path))

            with open(extracted_path, "rb") as file_object:
                digest = hashlib.sha256(file_object.read()).hexdigest()

            hashes_file_path = os.path.join(target_path, "hashes.json")
            self.assertTrue(os.path.exists(hashes_file_path))
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual(digest, hashes[0]["sha256"])
            self.assertEqual(
                [
                    os.path.join("p1", "file_hardlink1"),
                    os.path.join("p1", "testdir1", "testfile1"),
                ],
                hashes[0]["paths"],
            )

    def testMainExtractIncludeDuplicates(self):
        """Tests main when duplicate data streams are included."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsHardlinks",
                    "--artifact_definitions",
                    artifact_definitions,
                    "--include_duplicates",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)

            paths = [
                os.path.join(target_path, "p1", "file_hardlink1"),
                os.path.join(target_path, "p1", "testdir1", "testfile1"),
            ]
            for extracted_path in paths:
                self.assertTrue(os.path.isfile(extracted_path))

            with open(paths[0], "rb") as file_object:
                first_contents = file_object.read()
            with open(paths[1], "rb") as file_object:
                second_contents = file_object.read()
            self.assertEqual(first_contents, second_contents)

            hashes_file_path = os.path.join(target_path, "hashes.json")
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual(
                hashlib.sha256(first_contents).hexdigest(),
                hashes[0]["sha256"],
            )
            self.assertEqual(
                [
                    os.path.join("p1", "file_hardlink1"),
                    os.path.join("p1", "testdir1", "testfile1"),
                ],
                hashes[0]["paths"],
            )

    def testMainExtractNameFilter(self):
        """Tests main when extracting files using a name filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--name_filter",
                    "file_hardlink1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/file_hardlink1 to: "
                f"{os.path.join(target_path, 'p1', 'file_hardlink1'):s}",
                result.stderr,
            )
            extracted_path = os.path.join(target_path, "p1", "file_hardlink1")
            self.assertTrue(os.path.isfile(extracted_path))

            hashes_file_path = os.path.join(target_path, "hashes.json")
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual([os.path.join("p1", "file_hardlink1")], hashes[0]["paths"])

    def testMainExtractExtensionFilter(self):
        """Tests main when extracting files using an extension filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--extension_filter",
                    "dat",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            destination_path = os.path.join(
                target_path, "p1", "System Volume Information", "WPSettings.dat"
            )
            self.assertIn(
                "Extracting: /p1/System Volume Information/WPSettings.dat to: "
                f"{destination_path:s}",
                result.stderr,
            )

            hashes_file_path = os.path.join(target_path, "hashes.json")
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual(
                [os.path.join("p1", "System Volume Information", "WPSettings.dat")],
                hashes[0]["paths"],
            )

    def testMainExtractTimeFilter(self):
        """Tests main when extracting files using a time filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            # The file entries in the image have modification times within
            # this time range.
            result = self._RunScript(
                [
                    "--time_filter",
                    "mtime,2019-01-01,2020-01-01",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{os.path.join(target_path, 'p1', 'testdir2', 'TestFile1'):s}",
                result.stderr,
            )

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            # This time range is after the modification times of all file
            # entries in the image, so no data streams should be extracted.
            result = self._RunScript(
                [
                    "--time_filter",
                    "mtime,2027-01-01,2028-01-01",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertNotIn("Extracting:", result.stderr)

            extracted_files = []
            for root, _, files in os.walk(target_path):
                for file_name in files:
                    if file_name == "hashes.json":
                        continue

                    extracted_files.append(os.path.join(root, file_name))

            self.assertEqual(0, len(extracted_files))

    def testMainExtractNoHashes(self):
        """Tests main when hashes are not generated."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "--no_hashes",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)

            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

            hashes_file_path = os.path.join(target_path, "hashes.json")
            self.assertFalse(os.path.exists(hashes_file_path))

    def testMainExtractSkipsExistingDestination(self):
        """Tests main when the destination of an extraction already exists."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            script_argv = [
                "--path",
                "/p1/testdir2/TestFile1",
                "-t",
                target_path,
                ntfs_image_path,
            ]

            result = self._RunScript(script_argv)
            self.assertEqual(0, result.returncode)
            self.assertIn("Extracting: /p1/testdir2/TestFile1 to:", result.stderr)

            result = self._RunScript(script_argv)
            self.assertEqual(0, result.returncode)
            self.assertNotIn("Extracting:", result.stderr)
            self.assertIn("skipped: destination file already exists:", result.stderr)

    def testMainExtractSkipsDestinationOutsideTarget(self):
        """Tests main when the destination path is not within the target path.

        A subdirectory within the target path that is a symbolic link to a
        location outside of the target path causes the sanitized destination
        path to be resolved outside of the target path.
        """
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with (
            test_lib.TempDirectory() as temp_dir,
            test_lib.TempDirectory() as outside_directory,
        ):
            target_path = os.path.join(temp_dir, "target")
            destination_directory = os.path.join(target_path, "p1", "testdir2")

            try:
                os.makedirs(os.path.dirname(destination_directory))
                os.symlink(outside_directory, destination_directory)
            except OSError:
                self.skipTest("unable to create a symbolic link")

            result = self._RunScript(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, result.returncode)
            self.assertIn("skipped:", result.stderr)
            self.assertIn("is not within target path", result.stderr)
            self.assertNotIn("Extracting:", result.stderr)

            self.assertFalse(
                os.path.isfile(os.path.join(outside_directory, "TestFile1"))
            )

            hashes_file_path = os.path.join(target_path, "hashes.json")
            self.assertTrue(os.path.exists(hashes_file_path))
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(0, len(hashes))

    def testMainExtractSkipsUnwritableDestination(self):
        """Tests main when the destination data stream cannot be written.

        The parent directory of the destination file is made read-only so
        that opening the file for writing fails with a permission error.
        """
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")
            destination_directory = os.path.join(target_path, "p1", "testdir2")
            os.makedirs(destination_directory)

            # The test relies on the permission to write to the directory
            # being denied, which systems such as Windows (running with
            # elevated privileges) or root may not provide.
            os.chmod(destination_directory, 0o500)
            try:
                with open(os.path.join(destination_directory, "TestFile1"), "wb"):
                    pass
            except OSError:
                pass
            else:
                os.chmod(destination_directory, 0o755)
                self.skipTest("unable to create a read-only directory")

            try:
                result = self._RunScript(
                    [
                        "--path",
                        "/p1/testdir2/TestFile1",
                        "-t",
                        target_path,
                        ntfs_image_path,
                    ]
                )

                self.assertEqual(0, result.returncode)
                self.assertIn("skipped:", result.stderr)
                self.assertIn("Permission denied", result.stderr)
                self.assertFalse(
                    os.path.isfile(os.path.join(destination_directory, "TestFile1"))
                )

                # The data stream was still hashed before the write failed,
                # so the hashes.json file contains its digest.
                hashes_file_path = os.path.join(target_path, "hashes.json")
                self.assertTrue(os.path.exists(hashes_file_path))
                with open(hashes_file_path, encoding="utf-8") as file_object:
                    hashes = json.load(file_object)

                self.assertEqual(1, len(hashes))
                self.assertEqual(
                    [os.path.join("p1", "testdir2", "TestFile1")],
                    hashes[0]["paths"],
                )
            finally:
                os.chmod(destination_directory, 0o755)

    def testMainExtractDefaultTargetPath(self):
        """Tests main when no target path is specified.

        The default target path is derived from the working directory and the
        name of the source image, therefore the script is run in the
        temporary directory.
        """
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            result = self._RunScript(
                ["--path", "/p1/testdir2/TestFile1", ntfs_image_path], cwd=temp_dir
            )

            self.assertEqual(0, result.returncode)

            target_path = os.path.join(temp_dir, "ntfs.vhd.extracted")
            self.assertTrue(os.path.isdir(target_path))

            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

    def testMainNoBasePathSpecs(self):
        """Tests main when no base path specifications were generated.

        A GPT image without valid partitions, stored as a static test data
        file, is scanned without generating any base path specification.
        """
        gpt_image_path = self._GetTestFilePath(["gpt.raw"])
        self._SkipIfPathNotExists(gpt_image_path)

        with test_lib.TempDirectory() as temp_dir:
            # Note that not all environments are able to scan such an image
            # as expected, e.g. when the versions of the underlying
            # libraries do not match.
            self._SkipIfGPTScenarioNotReproducible(gpt_image_path, 0)

            target_path = os.path.join(temp_dir, "target")

            result = self._RunScript(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "-t",
                    target_path,
                    gpt_image_path,
                ]
            )
            self.assertEqual(1, result.returncode)
            self.assertIn("No supported file system found in source.", result.stdout)

    def testMainScannerError(self):
        """Tests main when a scanner error occurs.

        An unreadable source file causes the scanner to fail.
        """
        with test_lib.TempDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "image.raw")
            with open(source_path, "wb") as file_object:
                file_object.write(b"garbage data")

            # The test relies on the permission to read the file being
            # denied, which systems such as Windows (running with elevated
            # privileges) or root may not provide.
            os.chmod(source_path, 0o000)
            try:
                with open(source_path, "rb"):
                    pass
            except OSError:
                pass
            else:
                os.chmod(source_path, 0o644)
                self.skipTest("unable to create an unreadable file")

            try:
                target_path = os.path.join(temp_dir, "target")
                result = self._RunScript(
                    [
                        "--path",
                        "/p1/testdir2/TestFile1",
                        "-t",
                        target_path,
                        source_path,
                    ]
                )

                self.assertEqual(1, result.returncode)
                self.assertIn("[ERROR] Unable to scan source", result.stderr)
            finally:
                os.chmod(source_path, 0o644)

    def testMainUserAbort(self):
        """Tests main when a user abort occurs.

        A GPT image with multiple partitions, stored as a static test data
        file, causes the script to prompt for the partition identifier(s).
        Note that a path filter that does not specify a partition is used,
        since a path filter with a partition would cause the partition to be
        selected without prompting. The prompt is aborted with a signal,
        which raises an interruption that is handled as a user abort.
        """
        if sys.platform == "win32":
            self.skipTest("sending a signal to the script is not supported")

        gpt_image_path = self._GetTestFilePath(["gpt2.raw"])
        self._SkipIfPathNotExists(gpt_image_path)

        with test_lib.TempDirectory() as temp_dir:
            # Note that not all environments are able to scan such an image
            # as expected, e.g. when the versions of the underlying
            # libraries do not match.
            self._SkipIfGPTScenarioNotReproducible(gpt_image_path, 2)

            target_path = os.path.join(temp_dir, "target")
            script_path = os.path.join(test_lib.PROJECT_PATH, self._SCRIPT_PATH)

            # The stdin pipe remains open and empty, so that the script
            # blocks in the partition identifier prompt.
            with subprocess.Popen(
                [
                    sys.executable,
                    script_path,
                    "--path",
                    "/testdir2/TestFile1",
                    "-t",
                    target_path,
                    gpt_image_path,
                ],
                env=self._GetSubprocessEnvironment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
            ) as process:
                prompt_reached = threading.Event()
                output_lines = []

                def _Reader():
                    """Reads the output of the subprocess."""
                    for line in process.stdout:
                        output_lines.append(line)
                        if "Please specify the identifier of the partition" in line:
                            prompt_reached.set()

                reader_thread = threading.Thread(target=_Reader, daemon=True)
                reader_thread.start()

                if not prompt_reached.wait(60):
                    process.kill()
                    process.wait()
                    self.skipTest("the partition identifier prompt did not appear")

                process.send_signal(signal.SIGINT)
                return_code = process.wait(timeout=60)

                reader_thread.join(timeout=10)

        output = "".join(output_lines)
        self.assertEqual(1, return_code)
        self.assertIn("Aborted by user.", output)


if __name__ == "__main__":
    unittest.main()
