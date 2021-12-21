#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Installation and deployment script."""

import glob
import os
import pkg_resources
import sys

try:
  from setuptools import setup
except ImportError:
  from distutils.core import setup

try:
  from distutils.command.bdist_msi import bdist_msi
except ImportError:
  bdist_msi = None

version_tuple = (sys.version_info[0], sys.version_info[1])
if version_tuple < (3, 6):
  print((
      'Unsupported Python version: {0:s}, version 3.6 or higher '
      'required.').format(sys.version))
  sys.exit(1)


if not bdist_msi:
  BdistMSICommand = None
else:
  class BdistMSICommand(bdist_msi):
    """Custom handler for the bdist_msi command."""

    # pylint: disable=invalid-name
    def run(self):
      """Builds an MSI."""
      # Command bdist_msi does not support the library version, neither a date
      # as a version but if we suffix it with .1 everything is fine.
      self.distribution.metadata.version += '.1'

      bdist_msi.run(self)


def parse_requirements_from_file(path):
  """Parses requirements from a requirements file.

  Args:
    path (str): path to the requirements file.

  Yields:
    str: name and optional version information of the required package.
  """
  with open(path, 'r') as file_object:
    file_contents = file_object.read()

  for requirement in pkg_resources.parse_requirements(file_contents):
    try:
      name = str(requirement.req)
    except AttributeError:
      name = str(requirement)

    if name.startswith('pip '):
      continue

    yield name


imagetools_description = (
    'Collection of tools to process storage media images')

imagetools_long_description = (
    'Collection of tools to process storage media images.')

setup(
    name='imagetools',
    version='20211221',
    description=imagetools_description,
    long_description=imagetools_long_description,
    license='Apache License, Version 2.0',
    url='https://github.com/log2timeline/imagetools',
    maintainer='Log2Timeline maintainers',
    maintainer_email='log2timeline-maintainers@googlegroups.com',
    cmdclass={
        'bdist_msi': BdistMSICommand},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    scripts=glob.glob(os.path.join('tools', '[a-z]*.py')),
    data_files=[
        ('share/doc/imagetools', [
            'LICENSE']),
    ],
    install_requires=parse_requirements_from_file('requirements.txt'),
    tests_require=parse_requirements_from_file('test_requirements.txt'),
)
