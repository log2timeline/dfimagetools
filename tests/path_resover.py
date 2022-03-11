#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for the helper for resolving paths."""

import unittest

from dfimagetools import path_resolver
from dfimagetools import resources

from tests import test_lib


class PathResolverTest(test_lib.BaseTestCase):
  """Tests for the path resolver."""

  # pylint: disable=protected-access

  def testExpandEnvironmentVariablesInPathSegments(self):
    """Tests the _ExpandEnvironmentVariablesInPathSegments function."""
    test_resolver = path_resolver.PathResolver()

    environment_variables = []

    environment_variable = resources.EnvironmentVariable(
        case_sensitive=False, name='allusersappdata',
        value='C:\\Documents and Settings\\All Users\\Application Data')
    environment_variables.append(environment_variable)

    environment_variable = resources.EnvironmentVariable(
        case_sensitive=False, name='allusersprofile',
        value='C:\\Documents and Settings\\All Users')
    environment_variables.append(environment_variable)

    environment_variable = resources.EnvironmentVariable(
        case_sensitive=False, name='SystemRoot', value='C:\\Windows')
    environment_variables.append(environment_variable)

    expected_path_segments = [
        '', 'Documents and Settings', 'All Users', 'Application Data',
        'Apache Software Foundation']

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%AllUsersAppData%', 'Apache Software Foundation'],
        environment_variables)
    self.assertEqual(path_segments, expected_path_segments)

    expected_path_segments = [
        '', 'Documents and Settings', 'All Users', 'Start Menu', 'Programs',
        'Startup']

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%AllUsersProfile%', 'Start Menu', 'Programs', 'Startup'],
        environment_variables)
    self.assertEqual(path_segments, expected_path_segments)

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%SystemRoot%', 'System32'], environment_variables)
    self.assertEqual(path_segments, ['', 'Windows', 'System32'])

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['C:', 'Windows', 'System32'], environment_variables)
    self.assertEqual(path_segments, ['', 'Windows', 'System32'])

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%SystemRoot%', 'System32'], None)
    self.assertEqual(path_segments, ['%SystemRoot%', 'System32'])

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%Bogus%', 'System32'], environment_variables)
    self.assertEqual(path_segments, ['%Bogus%', 'System32'])

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%%environ_systemroot%%', 'System32'], environment_variables)
    self.assertEqual(path_segments, ['', 'Windows', 'System32'])

    # Test non-string environment variable.
    environment_variables = []

    environment_variable = resources.EnvironmentVariable(
        case_sensitive=False, name='SystemRoot', value=('bogus', 0))
    environment_variables.append(environment_variable)

    path_segments = test_resolver._ExpandEnvironmentVariablesInPathSegments(
        ['%SystemRoot%', 'System32'], environment_variables)
    self.assertEqual(path_segments, ['%SystemRoot%', 'System32'])

  def testExpandUserDirectoryVariableInPathSegments(self):
    """Tests the _ExpandUserDirectoryVariableInPathSegments function."""
    test_resolver = path_resolver.PathResolver()

    user_account_artifact1 = resources.UserAccount(
        user_directory='/home/Test1', username='Test1')
    user_account_artifact2 = resources.UserAccount(
        user_directory='/Users/Test2', username='Test2')
    user_account_artifact3 = resources.UserAccount(username='Test3')

    user_accounts = [
        user_account_artifact1, user_account_artifact2, user_account_artifact3]

    path_segments = ['%%users.homedir%%', '.bashrc']
    expanded_paths = test_resolver._ExpandUserDirectoryVariableInPathSegments(
        path_segments, '/', user_accounts)

    expected_expanded_paths = [
        '/home/Test1/.bashrc',
        '/Users/Test2/.bashrc']
    self.assertEqual(expanded_paths, expected_expanded_paths)

    path_segments = ['%%users.homedir%%', '.bashrc']
    expanded_paths = test_resolver._ExpandUserDirectoryVariableInPathSegments(
        path_segments, '/', [])

    expected_expanded_paths = [
        '/Documents and Settings/*/.bashrc', '/home/*/.bashrc',
        '/Users/*/.bashrc']
    self.assertEqual(expanded_paths, expected_expanded_paths)

    user_account_artifact1 = resources.UserAccount(
        user_directory='C:\\Users\\Test1', user_directory_path_separator='\\',
        username='Test1')
    user_account_artifact2 = resources.UserAccount(
        user_directory='%SystemDrive%\\Users\\Test2',
        user_directory_path_separator='\\', username='Test2')

    user_accounts = [user_account_artifact1, user_account_artifact2]

    path_segments = ['%%users.userprofile%%', 'Profile']
    expanded_paths = test_resolver._ExpandUserDirectoryVariableInPathSegments(
        path_segments, '\\', user_accounts)

    expected_expanded_paths = [
        '\\Users\\Test1\\Profile',
        '\\Users\\Test2\\Profile']
    self.assertEqual(expanded_paths, expected_expanded_paths)

    path_segments = ['C:', 'Temp']
    expanded_paths = test_resolver._ExpandUserDirectoryVariableInPathSegments(
        path_segments, '\\', user_accounts)

    expected_expanded_paths = ['\\Temp']
    self.assertEqual(expanded_paths, expected_expanded_paths)

    path_segments = ['C:', 'Temp', '%%users.userprofile%%']
    expanded_paths = test_resolver._ExpandUserDirectoryVariableInPathSegments(
        path_segments, '\\', user_accounts)

    expected_expanded_paths = ['\\Temp\\%%users.userprofile%%']
    self.assertEqual(expanded_paths, expected_expanded_paths)

  def testExpandUsersVariableInPathSegments(self):
    """Tests the _ExpandUsersVariableInPathSegments function."""
    test_resolver = path_resolver.PathResolver()

    user_account_artifact1 = resources.UserAccount(
        identifier='1000', user_directory='C:\\Users\\Test1',
        user_directory_path_separator='\\', username='Test1')
    user_account_artifact2 = resources.UserAccount(
        identifier='1001', user_directory='%SystemDrive%\\Users\\Test2',
        user_directory_path_separator='\\', username='Test2')

    user_accounts = [user_account_artifact1, user_account_artifact2]

    path_segments = ['%%users.appdata%%', 'Microsoft', 'Windows', 'Recent']
    expanded_paths = test_resolver._ExpandUsersVariableInPathSegments(
        path_segments, '\\', user_accounts)

    expected_expanded_paths = [
        '\\Users\\Test1\\AppData\\Roaming\\Microsoft\\Windows\\Recent',
        '\\Users\\Test1\\Application Data\\Microsoft\\Windows\\Recent',
        '\\Users\\Test2\\AppData\\Roaming\\Microsoft\\Windows\\Recent',
        '\\Users\\Test2\\Application Data\\Microsoft\\Windows\\Recent']
    self.assertEqual(sorted(expanded_paths), expected_expanded_paths)

    path_segments = ['C:', 'Windows']
    expanded_paths = test_resolver._ExpandUsersVariableInPathSegments(
        path_segments, '\\', user_accounts)

    expected_expanded_paths = ['\\Windows']
    self.assertEqual(sorted(expanded_paths), expected_expanded_paths)

  def testIsWindowsDrivePathSegment(self):
    """Tests the _IsWindowsDrivePathSegment function."""
    test_resolver = path_resolver.PathResolver()

    result = test_resolver._IsWindowsDrivePathSegment('C:')
    self.assertTrue(result)

    result = test_resolver._IsWindowsDrivePathSegment('%SystemDrive%')
    self.assertTrue(result)

    result = test_resolver._IsWindowsDrivePathSegment('%%environ_systemdrive%%')
    self.assertTrue(result)

    result = test_resolver._IsWindowsDrivePathSegment('Windows')
    self.assertFalse(result)

  def testExpandEnvironmentVariables(self):
    """Tests the ExpandEnvironmentVariables function."""
    test_resolver = path_resolver.PathResolver()

    environment_variables = []

    environment_variable = resources.EnvironmentVariable(
        case_sensitive=False, name='SystemRoot', value='C:\\Windows')
    environment_variables.append(environment_variable)

    expanded_path = test_resolver.ExpandEnvironmentVariables(
        '%SystemRoot%\\System32', '\\', environment_variables)
    self.assertEqual(expanded_path, '\\Windows\\System32')

  def testExpandGlobStars(self):
    """Tests the ExpandGlobStars function."""
    test_resolver = path_resolver.PathResolver()

    paths = test_resolver.ExpandGlobStars('/etc/sysconfig/**', '/')

    self.assertEqual(len(paths), 10)

    expected_paths = sorted([
        '/etc/sysconfig/*',
        '/etc/sysconfig/*/*',
        '/etc/sysconfig/*/*/*',
        '/etc/sysconfig/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*/*/*/*'])
    self.assertEqual(sorted(paths), expected_paths)

    # Test globstar with recursion depth of 4.
    paths = test_resolver.ExpandGlobStars('/etc/sysconfig/**4', '/')

    self.assertEqual(len(paths), 4)

    expected_paths = sorted([
        '/etc/sysconfig/*',
        '/etc/sysconfig/*/*',
        '/etc/sysconfig/*/*/*',
        '/etc/sysconfig/*/*/*/*'])
    self.assertEqual(sorted(paths), expected_paths)

    # Test globstar with unsupported recursion depth of 99.
    paths = test_resolver.ExpandGlobStars('/etc/sysconfig/**99', '/')

    self.assertEqual(len(paths), 10)

    expected_paths = sorted([
        '/etc/sysconfig/*',
        '/etc/sysconfig/*/*',
        '/etc/sysconfig/*/*/*',
        '/etc/sysconfig/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*/*/*',
        '/etc/sysconfig/*/*/*/*/*/*/*/*/*/*'])
    self.assertEqual(sorted(paths), expected_paths)

    # Test globstar with prefix.
    paths = test_resolver.ExpandGlobStars('/etc/sysconfig/my**', '/')

    self.assertEqual(len(paths), 1)

    self.assertEqual(paths, ['/etc/sysconfig/my**'])

    # Test globstar with suffix.
    paths = test_resolver.ExpandGlobStars('/etc/sysconfig/**.exe', '/')

    self.assertEqual(len(paths), 1)

    self.assertEqual(paths, ['/etc/sysconfig/**.exe'])

  def testExpandUsersVariable(self):
    """Tests the ExpandUsersVariable function."""
    test_resolver = path_resolver.PathResolver()

    user_account_artifact1 = resources.UserAccount(
        user_directory='C:\\Users\\Test1', user_directory_path_separator='\\',
        username='Test1')
    user_account_artifact2 = resources.UserAccount(
        user_directory='%SystemDrive%\\Users\\Test2',
        user_directory_path_separator='\\', username='Test2')

    user_accounts = [user_account_artifact1, user_account_artifact2]

    path = '%%users.appdata%%\\Microsoft\\Windows\\Recent'
    expanded_paths = test_resolver.ExpandUsersVariable(
        path, '\\', user_accounts)

    expected_expanded_paths = [
        '\\Users\\Test1\\AppData\\Roaming\\Microsoft\\Windows\\Recent',
        '\\Users\\Test1\\Application Data\\Microsoft\\Windows\\Recent',
        '\\Users\\Test2\\AppData\\Roaming\\Microsoft\\Windows\\Recent',
        '\\Users\\Test2\\Application Data\\Microsoft\\Windows\\Recent']
    self.assertEqual(sorted(expanded_paths), expected_expanded_paths)


if __name__ == '__main__':
  unittest.main()
