#!/usr/bin/env python3
"""Tests for the console script to list file entries."""

import logging
import os
import sys
import unittest
from io import StringIO
from unittest import mock

import artifacts

from dfvfs.helpers import volume_scanner
from dfvfs.lib import errors as dfvfs_errors

from dfimagetools.scripts import list_file_entries

from tests import test_lib


class ListFileEntriesTest(test_lib.BaseTestCase):
    """Tests for the list file entries console script."""

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
        program_name = "list_file_entries.py"

        stdout = StringIO()
        stderr = StringIO()
        with mock.patch.object(sys, "argv", [program_name, *argv]):
            with mock.patch("sys.stdout", stdout):
                with mock.patch("sys.stderr", stderr):
                    self._ResetLogging()
                    exit_code = list_file_entries.Main()

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

    def testMainUnsupportedOutputFormat(self):
        """Tests main with an unsupported output format."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        exit_code, output, _ = self._RunMain(
            ["--output_format", "csv", ntfs_image_path]
        )
        self.assertEqual(1, exit_code)
        self.assertIn("Unsupported output format: csv.", output)

    def testMainArtifactFiltersWithoutDefinitions(self):
        """Tests main when artifact filters are specified without definitions."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        real_exists = os.path.exists

        def FakeExists(path):
            if path.replace("\\", "/") == "/usr/share/artifacts":
                return False

            return real_exists(path)

        with (
            mock.patch.object(artifacts, "__file__", "/usr/nonexistent/__init__.py"),
            mock.patch("os.path.exists", FakeExists),
        ):
            exit_code, output, _ = self._RunMain(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
                    ntfs_image_path,
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertIn(
            "[ERROR] artifact filters were specified but no paths to artifact "
            "definitions were provided.",
            output,
        )

    def testMainNoBasePathSpecs(self):
        """Tests main when no base path specifications were generated."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with mock.patch.object(
            volume_scanner.VolumeScanner, "GetBasePathSpecs", return_value=[]
        ):
            exit_code, output, _ = self._RunMain([ntfs_image_path])

        self.assertEqual(1, exit_code)
        self.assertIn("No supported file system found in source.", output)

    def testMainScannerError(self):
        """Tests main when a scanner error occurs."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with mock.patch.object(
            volume_scanner.VolumeScanner,
            "GetBasePathSpecs",
            side_effect=dfvfs_errors.ScannerError("Failed to open source"),
        ):
            exit_code, _, error_output = self._RunMain([ntfs_image_path])

        self.assertEqual(1, exit_code)
        self.assertIn("[ERROR] Failed to open source", error_output)

    def testMainUserAbort(self):
        """Tests main when a user abort occurs."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        with mock.patch.object(
            volume_scanner.VolumeScanner,
            "GetBasePathSpecs",
            side_effect=dfvfs_errors.UserAbort(),
        ):
            exit_code, _, error_output = self._RunMain([ntfs_image_path])

        self.assertEqual(1, exit_code)
        self.assertIn("Aborted by user.", error_output)

    def testMainArtifactFilterWithoutFindSpecs(self):
        """Tests main when an artifact filter does not generate find specs."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        exit_code, output, _ = self._RunMain(
            [
                "--artifact_filters",
                "UndefinedArtifactName",
                "--artifact_definitions",
                artifact_definitions,
                ntfs_image_path,
            ]
        )
        self.assertEqual(1, exit_code)
        self.assertIn(
            "[ERROR] an artifact filter was specified but no corresponding "
            "file system find specifications were generated.",
            output,
        )

    def testMainListBodyfile(self):
        """Tests main when listing all file entries in a bodyfile format."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        expected_output_path = self._GetTestFilePath(["ntfs.vhd.bodyfile"])
        self._SkipIfPathNotExists(expected_output_path)

        with open(expected_output_path, encoding="utf-8") as file_object:
            expected_output = file_object.read()

        exit_code, output, _ = self._RunMain(["--use_original_md5", ntfs_image_path])
        self.assertEqual(0, exit_code)

        expected_output = "# extended bodyfile 3 format\n" + expected_output
        self.assertEqual(expected_output, output)

    def testMainListBodyfileWithoutOriginalMD5(self):
        """Tests main when listing files without the original MD5 format."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        expected_output_path = self._GetTestFilePath(["ntfs.vhd.bodyfile"])
        self._SkipIfPathNotExists(expected_output_path)

        with open(expected_output_path, encoding="utf-8") as file_object:
            expected_lines = file_object.read().splitlines()

        exit_code, output, _ = self._RunMain([ntfs_image_path])
        self.assertEqual(0, exit_code)

        lines = output.splitlines()
        self.assertEqual(1 + len(expected_lines), len(lines))
        self.assertEqual("# extended bodyfile 3 format", lines[0])
        self.assertIn("N/A (skipped)", lines[1])

    def testMainListArtifactFilter(self):
        """Tests main when listing file entries based on artifact filters."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        exit_code, output, _ = self._RunMain(
            [
                "--artifact_filters",
                "TestNtfsTestDir2",
                "--artifact_definitions",
                artifact_definitions,
                "--use_original_md5",
                ntfs_image_path,
            ]
        )
        self.assertEqual(0, exit_code)

        lines = output.splitlines()
        self.assertEqual("# extended bodyfile 3 format", lines[0])

        # The two sources in the definition each match both files because the
        # NTFS volume is case-insensitive, and each file is listed along with
        # its associated FILE_NAME attribute:
        #   2 files x 2 sources x 2 lines + header = 9 lines
        self.assertEqual(9, len(lines))

        for line in lines[1:]:
            self.assertIn("/p1/testdir2/", line)

        # Both files referenced by the definition are listed.
        self.assertIn("TestFile1", output)
        self.assertIn("testfile1", output)

    def testMainListNoAliases(self):
        """Tests main when listing file entries without partition aliases."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        exit_code, output, _ = self._RunMain(["--no_aliases", ntfs_image_path])
        self.assertEqual(0, exit_code)

        lines = output.splitlines()
        self.assertEqual("# extended bodyfile 3 format", lines[0])
        self.assertIn("N/A (skipped)", lines[1])

        self.assertIn("|/p1/testdir2/TestFile1|", output)
        self.assertIn("|/p1/testdir2/testfile1|", output)

    def testMainListSectorSize(self):
        """Tests main when listing file entries with a sector size."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        exit_code, output, _ = self._RunMain(["--sector_size", "512", ntfs_image_path])
        self.assertEqual(0, exit_code)

        lines = output.splitlines()
        self.assertEqual("# extended bodyfile 3 format", lines[0])
        self.assertIn("|/p1/testdir2/TestFile1|", output)


if __name__ == "__main__":
    unittest.main()
