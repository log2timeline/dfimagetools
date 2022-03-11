# -*- coding: utf-8 -*-
"""Helper for filtering based on artifact definitions."""

import logging

from artifacts import definitions as artifacts_definitions

from dfvfs.helpers import file_system_searcher as dfvfs_file_system_searcher

from dfimagetools import path_resolver


class ArtifactDefinitionFiltersGenerator(object):
  """Generator of filters based on artifact definitions."""

  def __init__(self, artifacts_registry, environment_variables, user_accounts):
    """Initializes an artifact definition filters generator.

    Args:
      artifacts_registry (artifacts.ArtifactDefinitionsRegistry): artifact
          definitions registry.
      environment_variables (list[EnvironmentVariable]): environment variables.
      user_accounts (list[UserAccount]): user accounts.
    """
    super(ArtifactDefinitionFiltersGenerator, self).__init__()
    self._artifacts_registry = artifacts_registry
    self._environment_variables = environment_variables
    self._path_resolver = path_resolver.PathResolver()
    self._user_accounts = user_accounts

  def _BuildFindSpecsFromArtifactDefinition(self, name):
    """Builds find specifications from an artifact definition.

    Args:
      name (str): name of the artifact definition.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    definition = self._artifacts_registry.GetDefinitionByName(name)
    if not definition:
      definition = self._artifacts_registry.GetDefinitionByAlias(name)

    if not definition:
      logging.warning('Undefined artifact definition: {0:s}'.format(name))
    else:
      for source in definition.sources:
        source_type = source.type_indicator
        if source_type not in (
            artifacts_definitions.TYPE_INDICATOR_ARTIFACT_GROUP,
            artifacts_definitions.TYPE_INDICATOR_DIRECTORY,
            artifacts_definitions.TYPE_INDICATOR_FILE,
            artifacts_definitions.TYPE_INDICATOR_PATH):
          continue

        if source_type == artifacts_definitions.TYPE_INDICATOR_DIRECTORY:
          logging.warning((
              'Use of deprecated source type: directory in artifact '
              'definition: {0:s}').format(name))

        if source_type == artifacts_definitions.TYPE_INDICATOR_ARTIFACT_GROUP:
          for source_name in set(source.names):
            for find_spec in self._BuildFindSpecsFromArtifactDefinition(
                source_name):
              yield find_spec

        elif source_type in (
            artifacts_definitions.TYPE_INDICATOR_DIRECTORY,
            artifacts_definitions.TYPE_INDICATOR_FILE,
            artifacts_definitions.TYPE_INDICATOR_PATH):
          for source_path in set(source.paths):
            for find_spec in self._BuildFindSpecsFromFileSourcePath(
                source_path, source.separator):
              yield find_spec

  def _BuildFindSpecsFromFileSourcePath(self, source_path, path_separator):
    """Builds find specifications from a file source type.

    Args:
      source_path (str): file system path defined by the source.
      path_separator (str): file system path segment separator.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    for path_glob in self._path_resolver.ExpandGlobStars(
        source_path, path_separator):

      for path in self._path_resolver.ExpandUsersVariable(
          path_glob, path_separator, self._user_accounts):

        if '%' in path:
          path = self._path_resolver.ExpandEnvironmentVariables(
              path, path_separator, self._environment_variables)

        if not path.startswith(path_separator):
          continue

        try:
          find_spec = dfvfs_file_system_searcher.FindSpec(
              case_sensitive=False, location_glob=path,
              location_separator=path_separator)
        except ValueError as exception:
          logging.error((
              'Unable to build find specification for path: "{0:s}" with '
              'error: {1!s}').format(path, exception))
          continue

        yield find_spec

  def GetFindSpecs(self, names):
    """Retrieves find specifications for one or more artifact definitions.

    Args:
      names (list[str]): names of the artifact definitions to filter on.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    for name in set(names):
      for find_spec in self._BuildFindSpecsFromArtifactDefinition(name):
        yield find_spec
