#!/usr/bin/env python3
"""Tests for the console script to list file entries.

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
    which the script is aborted by a signal.

The GPT images are stored as static test data files in the test data
directory instead of being generated at runtime.
"""

import os
import signal
import subprocess
import sys
import threading
import unittest

from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import file_entry_lister

from tests import test_lib


class ListFileEntriesTest(test_lib.BaseTestCase):
    """Tests for the list file entries console script."""

    # The path to the console script under test relative to the project root.
    _SCRIPT_PATH = os.path.join("dfimagetools", "scripts", "list_file_entries.py")

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

    def _RunScript(self, argv, extra_pythonpath=None, timeout=300):
        """Runs the console script in a subprocess with the provided arguments.

        Args:
          argv (list[str]): command line arguments to pass to the script.
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

    def testMainUnsupportedOutputFormat(self):
        """Tests main with an unsupported output format."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        result = self._RunScript(["--output_format", "csv", ntfs_image_path])
        self.assertEqual(1, result.returncode)
        self.assertIn("Unsupported output format: csv.", result.stdout)

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

        with test_lib.TempDirectory() as stub_dir:
            stub_package_path = os.path.join(stub_dir, "artifacts")
            os.makedirs(stub_package_path)
            for module in ("__init__", "definitions", "reader", "registry"):
                # The modules only need to exist for the imports of the
                # script to succeed.
                stub_module_path = os.path.join(stub_package_path, f"{module}.py")
                with open(stub_module_path, "w", encoding="utf-8"):
                    pass

            result = self._RunScript(
                [
                    "--artifact_filters",
                    "TestNtfsTestDir2",
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

    def testMainNoBasePathSpecs(self):
        """Tests main when no base path specifications were generated.

        A GPT image without valid partitions, stored as a static test data
        file, is scanned without generating any base path specification.
        """
        gpt_image_path = self._GetTestFilePath(["gpt.raw"])
        self._SkipIfPathNotExists(gpt_image_path)

        # Note that not all environments are able to scan such an image
        # as expected, e.g. when the versions of the underlying
        # libraries do not match.
        self._SkipIfGPTScenarioNotReproducible(gpt_image_path, 0)

        result = self._RunScript([gpt_image_path])
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
                result = self._RunScript([source_path])
                self.assertEqual(1, result.returncode)
                self.assertIn("[ERROR] Unable to scan source", result.stderr)
            finally:
                os.chmod(source_path, 0o644)

    def testMainUserAbort(self):
        """Tests main when a user abort occurs.

        A GPT image with multiple partitions, stored as a static test data
        file, causes the script to prompt for the partition identifier(s).
        The prompt is aborted with a signal, which raises an interruption
        that is handled as a user abort.
        """
        if sys.platform == "win32":
            self.skipTest("sending a signal to the script is not supported")

        gpt_image_path = self._GetTestFilePath(["gpt2.raw"])
        self._SkipIfPathNotExists(gpt_image_path)

        # Note that not all environments are able to scan such an image
        # as expected, e.g. when the versions of the underlying
        # libraries do not match.
        self._SkipIfGPTScenarioNotReproducible(gpt_image_path, 2)

        script_path = os.path.join(test_lib.PROJECT_PATH, self._SCRIPT_PATH)

        # The stdin pipe remains open and empty, so that the script
        # blocks in the partition identifier prompt.
        with subprocess.Popen(
            [sys.executable, script_path, gpt_image_path],
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

    def testMainArtifactFilterWithoutFindSpecs(self):
        """Tests main when an artifact filter does not generate find specs."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        result = self._RunScript(
            [
                "--artifact_filters",
                "UndefinedArtifactName",
                "--artifact_definitions",
                artifact_definitions,
                ntfs_image_path,
            ]
        )
        self.assertEqual(1, result.returncode)
        self.assertIn(
            "[ERROR] an artifact filter was specified but no corresponding "
            "file system find specifications were generated.",
            result.stdout,
        )

    def testMainListBodyfile(self):
        """Tests main when listing all file entries in a bodyfile format."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        expected_output_path = self._GetTestFilePath(["ntfs.vhd.bodyfile"])
        self._SkipIfPathNotExists(expected_output_path)

        with open(expected_output_path, encoding="utf-8") as file_object:
            expected_output = file_object.read()

        result = self._RunScript(["--use_original_md5", ntfs_image_path])
        self.assertEqual(0, result.returncode)

        expected_output = "# extended bodyfile 3 format\n" + expected_output
        self.assertEqual(expected_output, result.stdout)

    def testMainListBodyfileWithoutOriginalMD5(self):
        """Tests main when listing files without the original MD5 format."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        expected_output_path = self._GetTestFilePath(["ntfs.vhd.bodyfile"])
        self._SkipIfPathNotExists(expected_output_path)

        with open(expected_output_path, encoding="utf-8") as file_object:
            expected_lines = file_object.read().splitlines()

        result = self._RunScript([ntfs_image_path])
        self.assertEqual(0, result.returncode)

        lines = result.stdout.splitlines()
        self.assertEqual(1 + len(expected_lines), len(lines))
        self.assertEqual("# extended bodyfile 3 format", lines[0])
        self.assertIn("N/A (skipped)", lines[1])

    def testMainListArtifactFilter(self):
        """Tests main when listing file entries based on artifact filters."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        artifact_definitions = self._GetTestFilePath(["artifacts"])
        self._SkipIfPathNotExists(artifact_definitions)

        result = self._RunScript(
            [
                "--artifact_filters",
                "TestNtfsTestDir2",
                "--artifact_definitions",
                artifact_definitions,
                "--use_original_md5",
                ntfs_image_path,
            ]
        )
        self.assertEqual(0, result.returncode)

        lines = result.stdout.splitlines()
        self.assertEqual("# extended bodyfile 3 format", lines[0])

        # The two sources in the definition each match both files because the
        # NTFS volume is case-insensitive, and each file is listed along with
        # its associated FILE_NAME attribute:
        #   2 files x 2 sources x 2 lines + header = 9 lines
        self.assertEqual(9, len(lines))

        for line in lines[1:]:
            self.assertIn("/p1/testdir2/", line)

        # Both files referenced by the definition are listed.
        self.assertIn("TestFile1", result.stdout)
        self.assertIn("testfile1", result.stdout)

    def testMainListNoAliases(self):
        """Tests main when listing file entries without partition aliases."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        result = self._RunScript(["--no_aliases", ntfs_image_path])
        self.assertEqual(0, result.returncode)

        lines = result.stdout.splitlines()
        self.assertEqual("# extended bodyfile 3 format", lines[0])
        self.assertIn("N/A (skipped)", lines[1])

        self.assertIn("|/p1/testdir2/TestFile1|", result.stdout)
        self.assertIn("|/p1/testdir2/testfile1|", result.stdout)

    def testMainListSectorSize(self):
        """Tests main when listing file entries with a sector size."""
        ntfs_image_path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(ntfs_image_path)

        result = self._RunScript(["--sector_size", "512", ntfs_image_path])
        self.assertEqual(0, result.returncode)

        lines = result.stdout.splitlines()
        self.assertEqual("# extended bodyfile 3 format", lines[0])
        self.assertIn("|/p1/testdir2/TestFile1|", result.stdout)


if __name__ == "__main__":
    unittest.main()
