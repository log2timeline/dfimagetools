#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the file entry list tool."""

import io
import os
import sys
import unittest

from tools import list_file_entries

from tests import test_lib


class OutputWriterTest(test_lib.BaseTestCase):
  """Tests for the output writer."""

  def testInitialize(self):
    """Tests the __init__ function."""
    output_writer = list_file_entries.OutputWriter()
    self.assertIsNotNone(output_writer)

  # TODO: add tests for _EncodeString


class FileOutputWriterTest(test_lib.BaseTestCase):
  """Tests for the file output writer."""

  def testWriteFileEntry(self):
    """Tests the WriteFileEntry function."""
    with test_lib.TempDirectory() as temp_directory:
      path = os.path.join(temp_directory, 'paths.txt')
      output_writer = list_file_entries.FileOutputWriter(path)

      output_writer.Open()
      output_writer.WriteFileEntry('/password.txt')
      output_writer.Close()

      with io.open(path, mode='rb') as file_object:
        output = file_object.read()

    expected_output = '/password.txt'.encode('utf-8')
    self.assertEqual(output.rstrip(), expected_output)


class StdoutWriterTest(test_lib.BaseTestCase):
  """Tests for the stdout output writer."""

  def testWriteFileEntry(self):
    """Tests the WriteFileEntry function."""
    with test_lib.TempDirectory() as temp_directory:
      original_stdout = sys.stdout

      path = os.path.join(temp_directory, 'hashes.txt')

      with io.open(path, mode='wt', encoding='utf-8') as file_object:
        sys.stdout = file_object

        output_writer = list_file_entries.StdoutWriter()

        output_writer.Open()
        output_writer.WriteFileEntry('/password.txt')
        output_writer.Close()

      sys.stdout = original_stdout

      with io.open(path, mode='rb') as file_object:
        output = file_object.read()

    expected_output = '/password.txt'.encode('utf-8')
    self.assertEqual(output.rstrip(), expected_output)


# TODO: add tests for Main


if __name__ == '__main__':
  unittest.main()
