#!/usr/bin/env python3
"""Tests for the console script to extract data streams."""

import hashlib
import json
import logging
import os
import sys
import unittest
from io import StringIO
from unittest import mock

import artifacts

from dfvfs.helpers import volume_scanner
from dfvfs.lib import errors as dfvfs_errors

from dfimagetools.scripts import extract_data_streams

from tests import test_lib


class ExtractDataStreamsTest(test_lib.BaseTestCase):
    """Tests for the extract data streams console script."""

    def setUp(self):
        """Setup the test case.

        The script under test calls logging.basicConfig, which is idempotent. The reset
        makes it possible to capture the logging output of each call in the (mocked)
        stderr stream that is active during that call.
        """
        super().setUp()
        self._original_handlers = logging.getLogger().handlers
        self._original_level = logging.getLogger().level

        logging.getLogger().handlers = []
        logging.getLogger().setLevel(logging.WARNING)

    def tearDown(self):
        """Tear down the test case."""
        logging.getLogger().handlers = self._original_handlers
        logging.getLogger().level = self._original_level

        super().tearDown()

    def _RunMain(self, argv):
        """Runs the Main function with the provided arguments.

        Args:
          argv (list[str]): command line arguments to pass to Main.

        Returns:
          tuple[int, str, str]: exit code, captured stdout and stderr.
        """
        program_name = "extract_data_streams.py"

        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(sys, "argv", [program_name, *argv]):
            with mock.patch("sys.stdout", stdout):
                with mock.patch("sys.stderr", stderr):
                    self._ResetLogging()
                    exit_code = extract_data_streams.Main()

        return exit_code, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def _ResetLogging():
        """Removes the root logger handlers.

        logging.basicConfig only takes effect when the root logger has no handlers. By
        clearing the handlers while the mocked stderr stream is active, the
        (re)configured handler is bound to that stream so the logging output of this
        call is captured.
        """
        logging.getLogger().handlers = []
        logging.getLogger().setLevel(logging.INFO)

    def testMainNoSource(self):
        """Tests main without a source image."""
        exit_code, output, _ = self._RunMain([])
        self.assertEqual(1, exit_code)
        self.assertIn("Source value is missing.", output)

    def testMainNoExtractionFilters(self):
        """Tests main without any extraction filters."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        exit_code, output, _ = self._RunMain([ntfs_image_path])
        self.assertEqual(1, exit_code)
        self.assertIn("[ERROR] no extraction filters were specified.", output)

    def testMainArtifactFiltersWithoutDefinitions(self):
        """Tests main when artifact filters are specified without definitions."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        real_exists = os.path.exists

        def FakeExists(path):
            if path == "/usr/share/artifacts":
                return False

            return real_exists(path)

        with (
            mock.patch.object(artifacts, "__file__", "/usr/nonexistent/__init__.py"),
            mock.patch("os.path.exists", FakeExists),
            test_lib.TempDirectory() as temp_dir,
        ):
            target_path = os.path.join(temp_dir, "target")
            exit_code, output, _ = self._RunMain(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertIn(
            "[ERROR] artifact filters were specified but no paths to artifact "
            "definitions were provided.",
            output,
        )

    def testMainTargetNotADirectory(self):
        """Tests main when the target path is a file instead of a directory."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")
            with open(target_path, "w", encoding="utf-8") as file_object:
                file_object.write("test")

            exit_code, output, _ = self._RunMain(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertIn("[ERROR] target path is not a directory.", output)

    def testMainUnsupportedTimeFilter(self):
        """Tests main with unsupported time filters."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            for time_filter in ("mtime,bad", "mtime,2019-13-45,2020-01-01"):
                exit_code, output, _ = self._RunMain(
                    [
                        "--time_filter",
                        time_filter,
                        "-t",
                        target_path,
                        ntfs_image_path,
                    ]
                )
                self.assertEqual(1, exit_code)
                self.assertIn("[ERROR] unsupported time filter:", output)

    def testMainExtractSingleFile(self):
        """Tests main when extracting a single file using a path filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            exit_code, _, error_output = self._RunMain(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{target_path:s}/p1/testdir2/TestFile1",
                error_output,
            )
            self.assertIn(f"Writing hashes.json to: {target_path:s}", error_output)

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
            self.assertEqual(["p1/testdir2/TestFile1"], hashes[0]["paths"])

    def testMainExtractSingleFileWithoutPartition(self):
        """Tests main when extracting a file using a partitionless path."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            exit_code, _, error_output = self._RunMain(
                [
                    "--path",
                    "/testdir2/TestFile1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{target_path:s}/p1/testdir2/TestFile1",
                error_output,
            )
            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

    def testMainExtractPathFilterOverridePartitions(self):
        """Tests main when a path filter overrides the --partitions option."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            exit_code, output, _ = self._RunMain(
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

            self.assertEqual(0, exit_code)
            self.assertIn(
                "[WARNING] partition specified in path filter will override "
                "--partitions command line argument.",
                output,
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

            exit_code, _, error_output = self._RunMain(
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

            self.assertEqual(0, exit_code)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{target_path:s}/p1/testdir2/TestFile1",
                error_output,
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
            hash_paths = sorted(path for hash in hashes for path in hash["paths"])
            self.assertEqual(
                [
                    "p1/testdir2/TestFile1",
                    "p1/testdir2/TestFile1",
                    "p1/testdir2/testfile1",
                    "p1/testdir2/testfile1",
                ],
                hash_paths,
            )
            self.assertNotEqual(hashes[0]["sha256"], hashes[1]["sha256"])

    def testMainExtractSkipsDuplicateDataStreams(self):
        """Tests main when duplicate data streams are skipped."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            exit_code, _, error_output = self._RunMain(
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

            self.assertEqual(0, exit_code)
            self.assertIn("Extracting: /p1/file_hardlink1 to:", error_output)
            self.assertIn("skipped: duplicate of", error_output)

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
                ["p1/file_hardlink1", "p1/testdir1/testfile1"],
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

            exit_code, _, _ = self._RunMain(
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

            self.assertEqual(0, exit_code)

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
                ["p1/file_hardlink1", "p1/testdir1/testfile1"],
                hashes[0]["paths"],
            )

    def testMainExtractNameFilter(self):
        """Tests main when extracting files using a name filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            exit_code, _, error_output = self._RunMain(
                [
                    "--name_filter",
                    "file_hardlink1",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertIn(
                "Extracting: /p1/file_hardlink1 to: "
                f"{target_path:s}/p1/file_hardlink1",
                error_output,
            )
            extracted_path = os.path.join(target_path, "p1", "file_hardlink1")
            self.assertTrue(os.path.isfile(extracted_path))

            hashes_file_path = os.path.join(target_path, "hashes.json")
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual(["p1/file_hardlink1"], hashes[0]["paths"])

    def testMainExtractExtensionFilter(self):
        """Tests main when extracting files using an extension filter."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            exit_code, _, error_output = self._RunMain(
                [
                    "--extension_filter",
                    "dat",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertIn(
                "Extracting: /p1/System Volume Information/WPSettings.dat to: "
                f"{target_path:s}/p1/System Volume Information/WPSettings.dat",
                error_output,
            )

            hashes_file_path = os.path.join(target_path, "hashes.json")
            with open(hashes_file_path, encoding="utf-8") as file_object:
                hashes = json.load(file_object)

            self.assertEqual(1, len(hashes))
            self.assertEqual(
                ["p1/System Volume Information/WPSettings.dat"],
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
            exit_code, _, error_output = self._RunMain(
                [
                    "--time_filter",
                    "mtime,2019-01-01,2020-01-01",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertIn(
                "Extracting: /p1/testdir2/TestFile1 to: "
                f"{target_path:s}/p1/testdir2/TestFile1",
                error_output,
            )

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            # This time range is after the modification times of all file
            # entries in the image, so no data streams should be extracted.
            exit_code, _, error_output = self._RunMain(
                [
                    "--time_filter",
                    "mtime,2027-01-01,2028-01-01",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertNotIn("Extracting:", error_output)

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

            exit_code, _, _ = self._RunMain(
                [
                    "--path",
                    "/p1/testdir2/TestFile1",
                    "--no_hashes",
                    "-t",
                    target_path,
                    ntfs_image_path,
                ]
            )

            self.assertEqual(0, exit_code)

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

            main_argv = [
                "--path",
                "/p1/testdir2/TestFile1",
                "-t",
                target_path,
                ntfs_image_path,
            ]

            exit_code, _, error_output = self._RunMain(main_argv)
            self.assertEqual(0, exit_code)
            self.assertIn("Extracting: /p1/testdir2/TestFile1 to:", error_output)

            exit_code, _, error_output = self._RunMain(main_argv)
            self.assertEqual(0, exit_code)
            self.assertNotIn("Extracting:", error_output)
            self.assertIn("skipped: destination file already exists:", error_output)

    def testMainExtractDefaultTargetPath(self):
        """Tests main when no target path is specified."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            with mock.patch("os.getcwd", return_value=temp_dir):
                exit_code, _, _ = self._RunMain(
                    ["--path", "/p1/testdir2/TestFile1", ntfs_image_path]
                )

            self.assertEqual(0, exit_code)

            target_path = os.path.join(temp_dir, "ntfs.vhd.extracted")
            self.assertTrue(os.path.isdir(target_path))

            extracted_path = os.path.join(target_path, "p1", "testdir2", "TestFile1")
            self.assertTrue(os.path.isfile(extracted_path))

    def testMainNoBasePathSpecs(self):
        """Tests main when no base path specifications were generated."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            with mock.patch.object(
                volume_scanner.VolumeScanner,
                "GetBasePathSpecs",
                return_value=[],
            ):
                exit_code, output, _ = self._RunMain(
                    [
                        "--path",
                        "/p1/testdir2/TestFile1",
                        "-t",
                        target_path,
                        ntfs_image_path,
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertIn("No supported file system found in source.", output)

    def testMainScannerError(self):
        """Tests main when a scanner error occurs."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            with mock.patch.object(
                volume_scanner.VolumeScanner,
                "GetBasePathSpecs",
                side_effect=dfvfs_errors.ScannerError("Failed to open source"),
            ):
                exit_code, _, error_output = self._RunMain(
                    [
                        "--path",
                        "/p1/testdir2/TestFile1",
                        "-t",
                        target_path,
                        ntfs_image_path,
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertIn("[ERROR] Failed to open source", error_output)

    def testMainUserAbort(self):
        """Tests main when a user abort occurs."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with test_lib.TempDirectory() as temp_dir:
            target_path = os.path.join(temp_dir, "target")

            with mock.patch.object(
                volume_scanner.VolumeScanner,
                "GetBasePathSpecs",
                side_effect=dfvfs_errors.UserAbort(),
            ):
                exit_code, _, error_output = self._RunMain(
                    [
                        "--path",
                        "/p1/testdir2/TestFile1",
                        "-t",
                        target_path,
                        ntfs_image_path,
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertIn("Aborted by user.", error_output)


if __name__ == "__main__":
    unittest.main()
