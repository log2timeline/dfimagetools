#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script to enumerate Docker containers.

Code is based on Docker-Explorer"""

import json
import os

from dfvfs.lib import definitions
from dfvfs.path import factory
from dfvfs.path import path_spec
from dfvfs.resolver import context
from dfvfs.resolver import resolver
from dfvfs.vfs import overlay_file_system


_DEFAULT_DOCKER_VERSION = 2

_resolver_context = context.Context()


class DockerContainer:
  """Class for a Docker container object.

  Attributes:
    config_image_name (str): the name of the container's image (eg: 'busybox').
    config_labels (list(str)): labels attached to the container.
    container_id (str): the ID of the container.
    creation_timestamp (str): the container's creation timestamp.
    docker_version (int): the version number of the storage system.
    image_id (str): the ID of the container's image.
    mount_points (list(dict)): list of mount points to bind from host to the
      container. (Docker storage backend v2).
    name (str): the name of the container.
    running (boolean): True if the container is running.
    start_timestamp (str): the container's start timestamp.
    storage_name (str): the container's storage driver name.
    storage_object (BaseStorage): the container's storage backend object.
    upper_dir (str): path to upper_dir folder.
    volumes (list(tuple)): list of mount points to bind from host to the
      container. (Docker storage backend v1).
    exposed_ports (dict): list of exposed ports from the container
  """

  CONFIG_FILENAME_MAP = {
      1: 'config.json',
      2: 'config.v2.json'
  }

  def __init__(self, container_spec, docker_instance,
               resolver_context=_resolver_context):
    """Initializes the Container class.

    Args:
      container_spec (path_spec.PathSpec): the path spec to the container
          directory in the docker folder.
      docker_instance (DockerInstance): the Docker instance the container
          belongs to.
      resolver_context (Optional[resolver.Context]): the resolver context.
    """
    self.container_spec = container_spec
    self.docker_instance = docker_instance

    if resolver_context:
      self.resolver_context = resolver_context
    else:
      resolver_context = resolver.Context()

    # build the path spec for the container config file
    config_file_segments = [self.container_spec.location]
    config_file_segments.append(
        self.CONFIG_FILENAME_MAP[self.docker_instance.docker_version])
    config_file_location = self.docker_instance.file_system.JoinPath(config_file_segments)

    self.config_path_spec = factory.Factory.NewPathSpec(
        type_indicator=self.container_spec.TYPE_INDICATOR, location=config_file_location,
        parent=self.container_spec.parent)

    self._ParseConfigFile()

    self._ParseMountId()

  def _GetDictValue(self, nested_dict, values):
    """Gets a value from a nested dictionary.

    Args:
      nested_dict (Dict[str, Any]): a nested dictionary where keys are all
          strings.
      values (List[str]): a list of key names, ordered from the root to desired
          key in the nested_dict.

    Returns:
      Any: the nested dictionary value or None if the desired key does not
          exist.
    """
    current = nested_dict
    for value in values:
      if not current or not isinstance(current, dict):
        return None
      if value not in current:
        return None
      current = current[value]
    return current

  def _ParseMountId(self):
    """Assumes overlay2."""
    # build the path spec for the container config file
    mount_id_segments = ['image']
    mount_id_segments.append(self.storage_driver)
    mount_id_segments.append('layerdb')
    mount_id_segments.append('mounts')
    mount_id_segments.append(self.identifier)
    mount_id_segments.append('mount-id')
    print(mount_id_segments)
    mount_id_spec = self.docker_instance.GetDockerDirectorySpec(
        mount_id_segments)

    mount_id_file_io = resolver.Resolver.OpenFileObject(
        mount_id_spec, self.resolver_context)

    self.mount_id = mount_id_file_io.read().decode()
    print(self.mount_id)

  def _ParseConfigFile(self):
    """Parses the container configuration file.

    Raises:
      ValueError: if there was an error when parsing the container
          configuration file.
    """
    container_file_io = resolver.Resolver.OpenFileObject(
        self.config_path_spec, self.resolver_context)

    #container_file_io = container_file.GetFileObject()
    container_info_dict = json.load(container_file_io)

    # Parse the 'Config' key, which relates to the Image configuration
    self.name = container_info_dict.get('Name')
    self.identifier = container_info_dict.get('ID')
    self.created = container_info_dict.get('Created')
    self.image_id = container_info_dict.get('Image')

    self.storage_driver = container_info_dict.get('Driver')

    if self.storage_driver is None:
      raise ValueError(f'{self.config_path_spec.location} lacks Driver key.')

    if self.storage_driver not in {'overlay2'}:
      raise ValueError(
          f'Unsupported Driver {self.storage_driver} in '
          f'{self.config_path_spec.location}.')

    self.running = self._GetDictValue(
        container_info_dict, ['State', 'Running'])
    self.started_at = self._GetDictValue(
        container_info_dict, ['State', 'StartedAt'])
    self.finished_at = self._GetDictValue(
        container_info_dict, ['State', 'FinishedAt'])

    self.config_image_name = self._GetDictValue(
        container_info_dict, ['Config', 'Image'])
    self.config_labels = self._GetDictValue(
        container_info_dict, ['Config', 'Labels'])
    self.creation_timestamp = self._GetDictValue(
        container_info_dict, ['Created'])
    self.image_id = self._GetDictValue(
        container_info_dict, ['Image'])

  def GetLowerLayerSpecs(self):
    """Gets the lower layer path specs of the container file system.

    Returns:
      List[path_spec.PathSpec]: a list of path specifications.
    """
    lower_directory_segments = [self.storage_driver,
                                self.mount_id,
                                'lower']
    lower_spec = self.docker_instance.GetDockerDirectorySpec(
        lower_directory_segments)
    lower_file_io = resolver.Resolver.OpenFileObject(
        lower_spec, self.resolver_context)
    lower_specs = lower_file_io.read().decode()

    path_specs = []
    for lower_spec_segment in lower_specs.split(':'):
      layer_segments = [self.storage_driver, lower_spec_segment]
      layer_spec = self.docker_instance.GetDockerDirectorySpec(layer_segments)
      layer_file_entry = resolver.Resolver.OpenFileEntry(
          layer_spec, self.resolver_context)

      layer_spec_segments = [self.storage_driver, 'l', layer_file_entry.link]
      path_spec = self.docker_instance.GetDockerDirectorySpec(
          layer_spec_segments)
      # TODO: is there another way to normalise path?
      path_spec.location = os.path.normpath(path_spec.location)
      path_specs.append(path_spec)
    return path_specs

  def GetUpperLayerSpec(self) -> path_spec.PathSpec:
    """Gets the upper layer of the container file system.

    Returns:
      path_spec.PathSpec: a path specification.
    """
    upper_directory_segments = [self.storage_driver,
                                self.mount_id,
                                'diff']
    return self.docker_instance.GetDockerDirectorySpec(upper_directory_segments)

  def GetOverlayFileSystem(self):
    """Returns the Overlay root path specification.

    Returns:
      overlay_file_system.OverlayFileSystem: the overlay file system."""

    lower_layer_specs = self.GetLowerLayerSpecs()
    upper_layer_spec = self.GetUpperLayerSpec()

    resolver_context = context.Context()
    overlay_path_spec = factory.Factory.NewPathSpec(
        type_indicator=definitions.TYPE_INDICATOR_OVERLAY,
        location='/')

    return overlay_file_system.OverlayFileSystem(
        resolver_context, overlay_path_spec,
        lower_layer_specs, upper_layer_spec)


class DockerInstance:
  """Class for a Docker instance object."""

  def __init__(self, path_spec, docker_version=_DEFAULT_DOCKER_VERSION,
               context=_resolver_context):
    """Initializes the DockerExplorer class.

    Args:
      path_spec (PathSpec): path specification for the docker instance.
      docker_version (int): the Docker version.
      context (resolver.Context): the resolver context.
    """
    self.file_system = resolver.Resolver.OpenFileSystem(path_spec)
    self.path_spec = path_spec
    self.docker_directory = path_spec.location
    self.docker_version = docker_version
    self.resolver_context = context

  def GetDockerDirectorySpec(self, subdirectory):
    """Returns a path spec for a subdirectory in the docker instance.

    Args:
      subdirectory (List[str]): the desired subdirectory.

    Returns:
      path_spec.PathSpec: the path specification for the subdirectory.
    """
    segments = [self.path_spec.location]
    segments.extend(subdirectory)
    location = self.file_system.JoinPath(segments)
    return factory.Factory.NewPathSpec(
        type_indicator=self.path_spec.TYPE_INDICATOR, location=location,
        parent=self.path_spec.parent)

  def GetContainerByIdentifier(self, container_id: str) -> DockerContainer:
    """Returns a Docker container specified by it's identifier.

    Args:
      container_id: the container ID.

    Returns:
      A DockerContainer object.

    Raises:
      ValueError: when the specified container ID does not exist.
    """
    container_spec = self.GetDockerDirectorySpec(['containers', container_id])

    if not self.file_system.FileEntryExistsByPathSpec(
        container_spec):
      raise ValueError('Container folder does not exist.')

    return DockerContainer(container_spec, self)

  def GetContainierEntries(self):
    """Returns the containers in the Docker instance.

    Returns:
      List[path_spec.PathSpec]: a list of path specifications for containers.
    """
    container_root_path_spec = self.GetDockerDirectorySpec(['containers'])

    container_root_file_entry = resolver.Resolver.OpenFileEntry(
        container_root_path_spec, self.resolver_context)

    if not container_root_file_entry.IsDirectory():
      return []  # TODO: raise error instead?

    return list(container_root_file_entry.sub_file_entries)
