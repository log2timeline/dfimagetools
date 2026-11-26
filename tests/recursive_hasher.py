#!/usr/bin/env python3
"""Tests for the helper to recursively calculate message digest hashes."""

import unittest

from dfimagetools import file_entry_lister
from dfimagetools import recursive_hasher

from tests import test_lib


class RecursiveHasherTest(test_lib.BaseTestCase):
    """Tests for the recursive hasher."""

    # pylint: disable=protected-access

    def _GetHashValues(self, path):
        """Retrieves the hash values of the data streams in a storage media image.

        Args:
          path (str): path of the storage media image.

        Returns:
          dict[str, str]: hash values per display path.
        """
        test_lister = file_entry_lister.FileEntryLister()
        base_path_specs = test_lister.GetBasePathSpecs(path)

        test_hasher = recursive_hasher.RecursiveHasher()

        hash_values = {}
        for file_entry, path_segments in test_lister.ListFileEntries(base_path_specs):
            for display_path, hash_value in test_hasher.CalculateHashesFileEntry(
                file_entry, path_segments
            ):
                hash_values[display_path] = hash_value

        return hash_values

    def testCalculateHashesFileEntry(self):
        """Tests the CalculateHashesFileEntry function."""
        path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(path)

        hash_values = self._GetHashValues(path)

        self.assertEqual(len(hash_values), 35)

        self.assertEqual(hash_values.get("/p1/$BadClus:$Bad"), "N/A (skipped)")

        self.assertEqual(
            hash_values.get("/p1/$BadClus"),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        self.assertEqual(
            hash_values.get("/p1/testdir1/testfile1"),
            "030a89d2fee52cf92a303025ea17ac1b9b1f37a4ce7d83f856c9504ae1678d1a",
        )

    def testGetLookupPath(self):
        """Tests the _GetLookupPath function."""
        path = self._GetTestFilePath(["ntfs.vhd"])
        self._SkipIfPathNotExists(path)

        test_lister = file_entry_lister.FileEntryLister()
        base_path_specs = test_lister.GetBasePathSpecs(path)

        test_hasher = recursive_hasher.RecursiveHasher()

        lookup_paths = []
        for file_entry, path_segments in test_lister.ListFileEntries(base_path_specs):
            if file_entry.name == "$BadClus":
                lookup_paths.append(
                    test_hasher._GetLookupPath(file_entry, path_segments)
                )

        self.assertEqual(lookup_paths, [("$BadClus",)])


if __name__ == "__main__":
    unittest.main()
