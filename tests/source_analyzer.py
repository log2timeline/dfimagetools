#!/usr/bin/env python3
"""Tests for the helper to volumes and file systems in a storage media image."""

import contextlib
import io
import unittest

from dfvfs.credentials import luksde_credentials
from dfvfs.helpers import source_scanner as dfvfs_source_scanner
from dfvfs.lib import definitions as dfvfs_definitions
from dfvfs.path import factory as path_spec_factory
from dfvfs.resolver import resolver as dfvfs_resolver

from dfimagetools import source_analyzer

from tests import test_lib


class TestVolumeScannerMediator:
    """Test volume scanner mediator.

    Attributes:
      unlock_calls (list[tuple[object, ...]]): calls to UnlockEncryptedVolume.
    """

    def __init__(self):
        """Initializes the test volume scanner mediator."""
        super().__init__()
        self.unlock_calls = []

    def UnlockEncryptedVolume(self, scanner, scan_context, scan_node, credentials):
        """Records the call to unlock an encrypted volume.

        Args:
          scanner (dfvfs.SourceScanner): the source scanner.
          scan_context (dfvfs.SourceScannerContext): the source scanner context.
          scan_node (dfvfs.SourceScanNode): the scan node.
          credentials (Optional[dfvfs.Credentials]): the credentials.
        """
        self.unlock_calls.append((scanner, scan_context, scan_node, credentials))


class TestFileSystem:
    """Test file system that reports a single file system type.

    Attributes:
      file_system_type (str): name of the Is-method that returns True, or an
          empty string if no file system type is reported.
    """

    def __init__(self, file_system_type):
        """Initializes the test file system.

        Args:
          file_system_type (str): name of the Is-method that returns True, or
              an empty string if no file system type is reported.
        """
        super().__init__()
        self.file_system_type = file_system_type

    def IsExt(self):
        """Determines if the file system is ext2/ext3/ext4.

        Returns:
          bool: True if file system type is IsExt, False if not.
        """
        return self.file_system_type == "IsExt"

    def IsFat(self):
        """Determines if the file system is FAT.

        Returns:
          bool: True if file system type is IsFat, False if not.
        """
        return self.file_system_type == "IsFat"

    def IsHFS(self):
        """Determines if the file system is HFS+/HFSX.

        Returns:
          bool: True if file system type is IsHFS, False if not.
        """
        return self.file_system_type == "IsHFS"

    def IsNTFS(self):
        """Determines if the file system is NTFS.

        Returns:
          bool: True if file system type is IsNTFS, False if not.
        """
        return self.file_system_type == "IsNTFS"


@contextlib.contextmanager
def _SwapOpenFileSystem(file_system):
    """Temporarily swaps the OpenFileSystem function of the resolver.

    Args:
      file_system (TestFileSystem): file system to return.

    Yields:
      None: context.
    """
    original_open_file_system = dfvfs_resolver.Resolver.OpenFileSystem

    def SwapOpenFileSystem(  # pylint: disable=unused-argument
        path_spec_object, resolver_context=None
    ):
        """Swaps the file system of the resolver.

        Args:
          path_spec_object (dfvfs.PathSpec): the path specification, unused.
          resolver_context (Optional[dfvfs.Context]): resolver context, unused.

        Returns:
          TestFileSystem: the file system.
        """
        return file_system

    dfvfs_resolver.Resolver.OpenFileSystem = SwapOpenFileSystem
    try:
        yield
    finally:
        dfvfs_resolver.Resolver.OpenFileSystem = original_open_file_system


class SourceAnalyzerTest(test_lib.BaseTestCase):
    """Tests for the source analyzer."""

    # pylint: disable=protected-access

    def testAnalyze(self):
        """Tests the Analyze function."""
        path = self._GetTestFilePath(["image.qcow2"])
        self._SkipIfPathNotExists(path)

        test_analyzer = source_analyzer.SourceAnalyzer()
        source_context = list(test_analyzer.Analyze(path))[0]

        self.assertIsNotNone(source_context)

    def testAnalyzeNonExistentSource(self):
        """Tests the Analyze function with a non-existent source."""
        test_analyzer = source_analyzer.SourceAnalyzer()

        with self.assertRaises(RuntimeError) as context:
            list(test_analyzer.Analyze("non-existent source"))

        self.assertIn("No such source: non-existent source.", str(context.exception))

    def testAnalyzeFileOrDirectorySource(self):
        """Tests the Analyze function when the source is a file or directory."""
        path = self._GetTestFilePath(["image.qcow2"])
        self._SkipIfPathNotExists(path)

        test_analyzer = source_analyzer.SourceAnalyzer(auto_recurse=False)

        def Scan(scan_context, **kwargs):  # pylint: disable=unused-argument
            """Simulates a scan that resolved the source to a file."""
            scan_context.source_type = dfvfs_definitions.SOURCE_TYPE_FILE
            scan_context.updated = True

        test_analyzer._source_scanner.Scan = Scan

        scan_contexts = list(test_analyzer.Analyze(path))

        # The scan terminates as soon as the source is a file or directory.
        self.assertEqual(len(scan_contexts), 1)
        self.assertEqual(
            scan_contexts[0].source_type, dfvfs_definitions.SOURCE_TYPE_FILE
        )

    def testAnalyzeWithoutAutoRecurse(self):
        """Tests the Analyze function without auto-recurse."""
        path = self._GetTestFilePath(["image.qcow2"])
        self._SkipIfPathNotExists(path)

        test_analyzer = source_analyzer.SourceAnalyzer(auto_recurse=False)
        scan_contexts = list(test_analyzer.Analyze(path))

        # Each scan step generates a scan context until there are no unscanned
        # scan nodes left.
        self.assertEqual(len(scan_contexts), 2)
        self.assertTrue(scan_contexts[0].HasFileSystemScanNodes())
        self.assertTrue(scan_contexts[1].HasFileSystemScanNodes())

        path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(path)

        test_analyzer = source_analyzer.SourceAnalyzer(auto_recurse=False)
        scan_contexts = list(test_analyzer.Analyze(path))

        self.assertEqual(len(scan_contexts), 2)

    def testAnalyzeWithLockedVolume(self):
        """Tests the Analyze function with a locked, i.e. encrypted, volume."""
        path = self._GetTestFilePath(["luks1.raw"])
        self._SkipIfPathNotExists(path)

        test_mediator = TestVolumeScannerMediator()
        test_analyzer = source_analyzer.SourceAnalyzer(mediator=test_mediator)
        scan_contexts = list(test_analyzer.Analyze(path))

        self.assertEqual(len(scan_contexts), 1)
        self.assertFalse(scan_contexts[0].HasFileSystemScanNodes())

        # The mediator should be used to unlock the locked volume.
        self.assertEqual(len(test_mediator.unlock_calls), 1)

        scanner, scan_context, scan_node, credentials = test_mediator.unlock_calls[0]

        self.assertIs(scanner, test_analyzer._source_scanner)
        self.assertIs(scan_context, scan_contexts[0])
        self.assertIn(scan_node, scan_context.locked_scan_nodes)
        self.assertEqual(
            scan_node.path_spec.type_indicator, dfvfs_definitions.TYPE_INDICATOR_LUKSDE
        )
        self.assertIsInstance(credentials, luksde_credentials.LUKSDECredentials)

    def testWriteScanNode(self):
        """Tests the WriteScanNode function."""
        path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(path)

        test_analyzer = source_analyzer.SourceAnalyzer()
        scan_context = list(test_analyzer.Analyze(path))[0]

        output_file_object = io.StringIO()
        with contextlib.redirect_stdout(output_file_object):
            test_analyzer.WriteScanNode(scan_context, scan_context.GetRootScanNode())

        expected_output = (
            f"OS: location: {path:s}\n"
            "  VHDI: \n"
            "    TSK_PARTITION: location: /\n"
            "      TSK_PARTITION: 0, start offset: 0 (0x00000000)\n"
            "      TSK_PARTITION: 1, start offset: 0 (0x00000000)\n"
            "      TSK_PARTITION: 2, start offset: 65536 (0x00010000), "
            "location: /p1\n"
            "        NTFS: location: \\\n"
            "      TSK_PARTITION: 3, start offset: 3145728 (0x00300000)\n"
        )
        self.assertEqual(expected_output, output_file_object.getvalue())

    def testWriteScanNodeWithoutScanNode(self):
        """Tests the WriteScanNode function without a scan node."""
        test_analyzer = source_analyzer.SourceAnalyzer()
        scan_context = dfvfs_source_scanner.SourceScannerContext()

        output_file_object = io.StringIO()
        with contextlib.redirect_stdout(output_file_object):
            test_analyzer.WriteScanNode(scan_context, None)

        self.assertEqual("", output_file_object.getvalue())

    def testWriteScanNodeWithLockedScanNode(self):
        """Tests the WriteScanNode function with a locked scan node."""
        path = self._GetTestFilePath(["luks1.raw"])
        self._SkipIfPathNotExists(path)

        test_mediator = TestVolumeScannerMediator()
        test_analyzer = source_analyzer.SourceAnalyzer(mediator=test_mediator)
        scan_context = list(test_analyzer.Analyze(path))[0]

        self.assertEqual(len(scan_context.locked_scan_nodes), 1)
        scan_node = scan_context.locked_scan_nodes[0]

        output_file_object = io.StringIO()
        with contextlib.redirect_stdout(output_file_object):
            test_analyzer.WriteScanNode(scan_context, scan_node)

        self.assertEqual("LUKSDE:  [LOCKED]\n", output_file_object.getvalue())

    def testWriteScanNodeWithVShadowScanNode(self):
        """Tests the WriteScanNode function with a VShadow scan node."""
        test_analyzer = source_analyzer.SourceAnalyzer()
        scan_context = dfvfs_source_scanner.SourceScannerContext()

        root_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_OS, location="C:\\Windows"
        )
        vshadow_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_VSHADOW,
            location="VshadowCopy",
            parent=root_path_spec,
            store_index=3,
        )
        scan_node = dfvfs_source_scanner.SourceScanNode(vshadow_path_spec)

        output_file_object = io.StringIO()
        with contextlib.redirect_stdout(output_file_object):
            test_analyzer.WriteScanNode(scan_context, scan_node)

        self.assertEqual(
            "VSHADOW: 3, location: VshadowCopy\n",
            output_file_object.getvalue(),
        )

    def testWriteScanNodeWithFileSystemScanNode(self):
        """Tests the WriteScanNode function with a TSK file system scan node."""
        test_analyzer = source_analyzer.SourceAnalyzer()
        scan_context = dfvfs_source_scanner.SourceScannerContext()

        root_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_OS, location="."
        )
        tsk_path_spec = path_spec_factory.Factory.NewPathSpec(
            dfvfs_definitions.TYPE_INDICATOR_TSK,
            location="/testfile",
            parent=root_path_spec,
        )
        scan_node = dfvfs_source_scanner.SourceScanNode(tsk_path_spec)

        expected_flags = (
            ("IsExt", " [ext2/ext3/ext4]"),
            ("IsFat", " [FAT-12/FAT-16/FAT-32]"),
            ("IsHFS", " [HFS+/HFSX]"),
            ("IsNTFS", " [NTFS]"),
            # An unsupported file system type results in no file system flag.
            ("", ""),
        )
        for is_method, expected_flag in expected_flags:
            with _SwapOpenFileSystem(TestFileSystem(is_method)):
                output_file_object = io.StringIO()
                with contextlib.redirect_stdout(output_file_object):
                    test_analyzer.WriteScanNode(scan_context, scan_node)

            self.assertIn(
                f"TSK: location: /testfile{expected_flag:s}",
                output_file_object.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
