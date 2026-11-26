#!/usr/bin/env python3
"""Tests for the dfVFS back-end helper functions."""

import unittest
import warnings

from dfvfs.lib import definitions as dfvfs_definitions

from dfimagetools import helpers
from dfimagetools import scripts
from dfimagetools.helpers import backend

from tests import test_lib


class SetDFVFSBackEndTest(test_lib.BaseTestCase):
    """Tests for the SetDFVFSBackEnd functions."""

    _PREFERRED_BACK_END_NAMES = [
        "PREFERRED_APM_BACK_END",
        "PREFERRED_EXT_BACK_END",
        "PREFERRED_FAT_BACK_END",
        "PREFERRED_GPT_BACK_END",
        "PREFERRED_HFS_BACK_END",
        "PREFERRED_NTFS_BACK_END",
    ]

    def setUp(self):
        """Saves the dfVFS preferred back-ends before each test."""
        self._preferred_back_ends = {
            name: getattr(dfvfs_definitions, name)
            for name in self._PREFERRED_BACK_END_NAMES
        }

    def tearDown(self):
        """Restores the dfVFS preferred back-ends after each test."""
        for name, value in self._preferred_back_ends.items():
            setattr(dfvfs_definitions, name, value)

    def _AssertTSKBackEnd(self):
        """Asserts that the TSK back-end is preferred."""
        self.assertEqual(
            dfvfs_definitions.PREFERRED_APM_BACK_END,
            dfvfs_definitions.TYPE_INDICATOR_TSK,
        )
        self.assertEqual(
            dfvfs_definitions.PREFERRED_EXT_BACK_END,
            dfvfs_definitions.TYPE_INDICATOR_TSK,
        )
        self.assertEqual(
            dfvfs_definitions.PREFERRED_FAT_BACK_END,
            dfvfs_definitions.TYPE_INDICATOR_TSK,
        )
        self.assertEqual(
            dfvfs_definitions.PREFERRED_GPT_BACK_END,
            dfvfs_definitions.TYPE_INDICATOR_TSK_PARTITION,
        )
        self.assertEqual(
            dfvfs_definitions.PREFERRED_HFS_BACK_END,
            dfvfs_definitions.TYPE_INDICATOR_TSK,
        )
        self.assertEqual(
            dfvfs_definitions.PREFERRED_NTFS_BACK_END,
            dfvfs_definitions.TYPE_INDICATOR_TSK,
        )

    def testSetDFVFSBackEnd(self):
        """Tests the SetDFVFSBackEnd function."""
        backend.SetDFVFSBackEnd("TSK")
        self._AssertTSKBackEnd()

    def testSetDFVFSBackEndDeprecatedHelpers(self):
        """Tests the deprecated SetDFVFSBackEnd function in helpers."""
        with warnings.catch_warnings(record=True):
            helpers.SetDFVFSBackEnd("TSK")

        self._AssertTSKBackEnd()

    def testSetDFVFSBackEndDeprecatedScripts(self):
        """Tests the deprecated SetDFVFSBackEnd function in scripts."""
        with warnings.catch_warnings(record=True):
            scripts.SetDFVFSBackEnd("TSK")

        self._AssertTSKBackEnd()


if __name__ == "__main__":
    unittest.main()
