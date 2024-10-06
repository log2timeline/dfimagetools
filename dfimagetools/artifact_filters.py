# -*- coding: utf-8 -*-
"""Helper for filtering based on artifact definitions."""

import logging

from artifacts import definitions as artifacts_definitions

from dfvfs.helpers import file_system_searcher as dfvfs_file_system_searcher

from dfimagetools import path_resolver


class ArtifactDefinitionFiltersGenerator(object):
  """Generator of filters based on artifact definitions."""

  # TODO: passing environment_variables and user_accounts via __init__ is
  # deprecated.

  def __init__(
      self, artifacts_registry, environment_variables=None, user_accounts=None):
    """Initializes an artifact definition filters generator.

    Args:
      artifacts_registry (artifacts.ArtifactDefinitionsRegistry): artifact
          definitions registry.
      environment_variables (Optional[list[EnvironmentVariable]]): environment
          variables.
      user_accounts (Optional[list[UserAccount]]]): user accounts.
    """
    super(ArtifactDefinitionFiltersGenerator, self).__init__()
    self._artifacts_registry = artifacts_registry
    self._environment_variables = environment_variables
    self._path_resolver = path_resolver.PathResolver()
    self._user_accounts = user_accounts

  def _BuildFindSpecsFromArtifactDefinition(
      self, name, environment_variables=None, user_accounts=None):
    """Builds find specifications from an artifact definition.

    Args:
      name (str): name of the artifact definition.
      environment_variables (Optional[list[EnvironmentVariable]]): environment
          variables.
      user_accounts (Optional[list[UserAccount]]): user accounts.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    definition = self._artifacts_registry.GetDefinitionByName(name)
    if not definition:
      definition = self._artifacts_registry.GetDefinitionByAlias(name)

    if not definition:
      logging.warning(f'Undefined artifact definition: {name:s}')
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
              f'Use of deprecated source type: directory in artifact '
              f'definition: {name:s}'))

        if source_type == artifacts_definitions.TYPE_INDICATOR_ARTIFACT_GROUP:
          for source_name in set(source.names):
            yield from self._BuildFindSpecsFromArtifactDefinition(
                source_name, environment_variables=environment_variables,
                user_accounts=user_accounts)

        elif source_type in (
            artifacts_definitions.TYPE_INDICATOR_DIRECTORY,
            artifacts_definitions.TYPE_INDICATOR_FILE,
            artifacts_definitions.TYPE_INDICATOR_PATH):
          for source_path in set(source.paths):
            yield from self._BuildFindSpecsFromFileSourcePath(
                source_path, source.separator,
                environment_variables=environment_variables,
                user_accounts=user_accounts)

  def _BuildFindSpecsFromFileSourcePath(
      self, source_path, path_separator, environment_variables=None,
      user_accounts=None):
    """Builds find specifications from a file source type.

    Args:
      source_path (str): file system path defined by the source.
      path_separator (str): file system path segment separator.
      environment_variables (Optional[list[EnvironmentVariable]]): environment
          variables.
      user_accounts (Optional[list[UserAccount]]): user accounts.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    for path_glob in self._path_resolver.ExpandGlobStars(
        source_path, path_separator):

      for path in self._path_resolver.ExpandUsersVariable(
          path_glob, path_separator, user_accounts):

        if '%' in path:
          path = self._path_resolver.ExpandEnvironmentVariables(
              path, path_separator, environment_variables)

        if not path.startswith(path_separator):
          continue

        try:
          find_spec = dfvfs_file_system_searcher.FindSpec(
              case_sensitive=False, location_glob=path,
              location_separator=path_separator)
        except ValueError as exception:
          logging.error((
              f'Unable to build find specification for path: "{path:s}" with '
              f'error: {exception!s}'))
          continue

        yield find_spec

  def GetFindSpecs(
      self, names=None, environment_variables=None, user_accounts=None):
    """Retrieves find specifications for one or more artifact definitions.

    Args:
      names (Optional[list[str]]): names of the artifact definitions to filter
          on.
      environment_variables (Optional[list[EnvironmentVariable]]): environment
          variables.
      user_accounts (Optional[list[UserAccount]]): user accounts.

    Yields:
      dfvfs.FindSpec: file system (dfVFS) find specification.
    """
    if self._environment_variables:
      environment_variables = self._environment_variables
    if self._user_accounts:
      user_accounts = self._user_accounts

    for name in set(names or []):
      yield from self._BuildFindSpecsFromArtifactDefinition(
          name, environment_variables=environment_variables,
          user_accounts=user_accounts)
