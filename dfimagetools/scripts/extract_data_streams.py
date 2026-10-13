#!/usr/bin/env python3
"""Console script to extract data streams."""

import argparse
import json
import logging
import os
import sys

import artifacts

from artifacts import reader as artifacts_reader
from artifacts import registry as artifacts_registry

from dfvfs.lib import errors as dfvfs_errors

from dfimagetools import artifact_filters
from dfimagetools import data_stream_writer
from dfimagetools import file_entry_lister
from dfimagetools import path_filters
from dfimagetools import windows_registry
from dfimagetools.helpers import command_line


def Main():
    """Entry point of console script to extract data streams.

    Returns:
      int: exit code that is provided to sys.exit().
    """
    argument_parser = argparse.ArgumentParser(
        description=("Extracts data streams from a storage media image.")
    )
    # TODO: add filter group
    argument_parser.add_argument(
        "--artifact_definitions",
        "--artifact-definitions",
        dest="artifact_definitions",
        type=str,
        metavar="PATH",
        action="store",
        help=(
            "Path to a directory or file containing the artifact definition .yaml "
            "files."
        ),
    )
    argument_parser.add_argument(
        "--artifact_filters",
        "--artifact-filters",
        dest="artifact_filters",
        type=str,
        default=None,
        metavar="NAMES",
        action="store",
        help="Comma separated list of names of artifact definitions to extract.",
    )
    argument_parser.add_argument(
        "--custom_artifact_definitions",
        "--custom-artifact-definitions",
        dest="custom_artifact_definitions",
        type=str,
        metavar="PATH",
        action="store",
        help=(
            "Path to a directory or file containing custom artifact definition .yaml "
            "files. "
        ),
    )
    argument_parser.add_argument(
        "--path",
        dest="path_filter",
        type=str,
        default=None,
        metavar="PATH",
        action="store",
        help="Path of data stream to extract.",
    )
    # TODO: add output group
    argument_parser.add_argument(
        "--no_aliases",
        "--no-aliases",
        dest="use_aliases",
        action="store_false",
        default=True,
        help=(
            "Disable the use of partition and/or volume aliases such as "
            "/apfs{f449e580-e355-4e74-8880-05e46e4e3b1e} and use indices such as "
            "/apfs1 instead."
        ),
    )
    argument_parser.add_argument(
        "--sector_size",
        "--sector-size",
        dest="sector_size",
        action="store",
        metavar="SIZE",
        type=int,
        default=None,
        help="number of bytes per sector.",
    )
    argument_parser.add_argument(
        "-t",
        "--target",
        dest="target",
        action="store",
        metavar="PATH",
        default=None,
        help=(
            "target (or destination) path of a directory where the extracted data "
            "streams should be stored."
        ),
    )
    argument_parser.add_argument(
        "--include_duplicates",
        "--include-duplicates",
        dest="include_duplicates",
        action="store_true",
        default=False,
        help=(
            "By default a digest hash (SHA-256) is calculated for each file "
            "(data stream). These hashes are compared to the previously "
            "extracted files and duplicates are skipped. Use this option to "
            "include duplicate files in the extraction."
        ),
    )
    argument_parser.add_argument(
        "--no_hashes",
        "--no-hashes",
        dest="no_hashes",
        action="store_true",
        default=False,
        help="Do not generate the hashes.json file.",
    )
    # TODO: add source group
    command_line.AddStorageMediaImageCLIArguments(argument_parser)

    argument_parser.add_argument(
        "source",
        nargs="?",
        action="store",
        metavar="image.raw",
        default=None,
        help="path of the storage media image.",
    )
    options = argument_parser.parse_args()

    if not options.source:
        print("Source value is missing.")
        print("")
        argument_parser.print_help()
        print("")
        return 1

    if options.artifact_filters:
        artifact_definitions = options.artifact_definitions
        if not artifact_definitions:
            artifact_definitions = os.path.join(
                os.path.dirname(artifacts.__file__), "data"
            )
            if not os.path.exists(artifact_definitions):
                artifact_definitions = os.path.join("/", "usr", "share", "artifacts")
            if not os.path.exists(artifact_definitions):
                artifact_definitions = None

        if not artifact_definitions and not options.custom_artifact_definitions:
            print(
                "[ERROR] artifact filters were specified but no paths to artifact "
                "definitions were provided."
            )
            print("")
            return 1

    elif not options.path_filter:
        print("[ERROR] no extraction filters were specified.")
        print("")
        return 1

    target_path = options.target
    if not target_path:
        source_name = os.path.basename(options.source)
        target_path = os.path.join(os.getcwd(), f"{source_name:s}.extracted")

    if not os.path.exists(target_path):
        os.makedirs(target_path)

    elif not os.path.isdir(target_path):
        print("[ERROR] target path is not a directory.")
        print("")
        return 1

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    mediator, volume_scanner_options = command_line.ParseStorageMediaImageCLIArguments(
        options
    )
    if options.artifact_filters:
        registry = artifacts_registry.ArtifactDefinitionsRegistry()
        reader = artifacts_reader.YamlArtifactsReader()

        if artifact_definitions:
            if os.path.isdir(artifact_definitions):
                registry.ReadFromDirectory(reader, artifact_definitions)
            elif os.path.isfile(artifact_definitions):
                registry.ReadFromFile(reader, artifact_definitions)

        if options.custom_artifact_definitions:
            if os.path.isdir(options.custom_artifact_definitions):
                registry.ReadFromDirectory(reader, options.custom_artifact_definitions)
            elif os.path.isfile(options.custom_artifact_definitions):
                registry.ReadFromFile(reader, options.custom_artifact_definitions)

        filter_generator = artifact_filters.ArtifactDefinitionFiltersGenerator(registry)

    elif options.path_filter:
        filter_generator = path_filters.PathFiltersGenerator(options.path_filter)

        if filter_generator.partition and options.partitions:
            print(
                "[WARNING] partition specified in path filter will override "
                "--partitions command line argument."
            )
            print("")

        if filter_generator.partition:
            volume_scanner_options.partitions = [filter_generator.partition]

    entry_lister = file_entry_lister.FileEntryLister(
        mediator=mediator,
        sector_size=options.sector_size,
        use_aliases=options.use_aliases,
    )
    find_specs_generated = False

    # A map between data stream SHA-256 digests and the relative paths of data
    # streams extracted from the source.
    relative_paths_by_digest = {}

    # A map between data stream SHA-256 digests and the display path of the
    # data stream that was first extracted with that digest.
    first_extraction_by_digest = {}

    # Hashing is only needed for de-duplication or generating the hashes.json
    # file.
    hash_data_streams = not (options.include_duplicates and options.no_hashes)

    try:
        base_path_specs = entry_lister.GetBasePathSpecs(
            options.source, options=volume_scanner_options
        )
        if not base_path_specs:
            print("No supported file system found in source.")
            print("")
            return 1

        for base_path_spec in base_path_specs:
            find_specs = []

            if options.artifact_filters:
                environment_variables = []
                user_accounts = []

                windows_directory = entry_lister.GetWindowsDirectory(base_path_spec)
                if windows_directory:
                    winregistry_collector = windows_registry.WindowsRegistryCollector(
                        base_path_spec, windows_directory
                    )
                    environment_variables = (
                        winregistry_collector.CollectSystemEnvironmentVariables()
                    )

                # TODO: determine user accounts.

                names = options.artifact_filters.split(",")
                find_specs = list(
                    filter_generator.GetFindSpecs(
                        names=names,
                        environment_variables=environment_variables,
                        user_accounts=user_accounts,
                    )
                )

            elif options.path_filter:
                find_specs = list(filter_generator.GetFindSpecs())

            if filter_generator:
                if not find_specs:
                    continue

                find_specs_generated = True

            file_entries_generator = entry_lister.ListFileEntriesWithFindSpecs(
                [base_path_spec], find_specs
            )
            stream_writer = data_stream_writer.DataStreamWriter()

            for file_entry, path_segments in file_entries_generator:
                for data_stream in file_entry.data_streams:
                    display_path = stream_writer.GetDisplayPath(
                        path_segments, data_stream.name
                    )
                    try:
                        destination_path = stream_writer.GetSanitizedPath(
                            path_segments, data_stream.name, target_path
                        )
                    except ValueError as exception:
                        logging.warning(f"{display_path:s} skipped: {exception!s}")
                        continue

                    digest = None
                    if hash_data_streams:
                        try:
                            digest = stream_writer.CalculateHash(
                                file_entry, data_stream.name
                            )
                        except (OSError, dfvfs_errors.BackEndError) as exception:
                            logging.warning(f"{display_path:s} skipped: {exception!s}")
                            continue

                        relative_paths_by_digest.setdefault(digest, []).append(
                            os.path.relpath(destination_path, target_path)
                        )

                        if not options.include_duplicates:
                            first_extraction = first_extraction_by_digest.get(digest)
                            if first_extraction:
                                logging.warning(
                                    f"{display_path:s} skipped: duplicate of "
                                    f"{first_extraction:s} with hash: {digest:s}"
                                )
                                continue

                    if os.path.exists(destination_path):
                        logging.warning(
                            f"{display_path:s} skipped: destination file already "
                            f"exists: {destination_path:s}"
                        )
                        continue

                    if digest and not options.include_duplicates:
                        first_extraction_by_digest[digest] = display_path

                    logging.info(
                        f"Extracting: {display_path:s} to: {destination_path:s}"
                    )
                    destination_directory = os.path.dirname(destination_path)
                    os.makedirs(destination_directory, exist_ok=True)

                    try:
                        stream_writer.WriteDataStream(
                            file_entry, data_stream.name, destination_path
                        )
                    except (OSError, dfvfs_errors.BackEndError) as exception:
                        logging.warning(f"{display_path:s} skipped: {exception!s}")
                        break

    except dfvfs_errors.ScannerError as exception:
        print(f"[ERROR] {exception!s}", file=sys.stderr)
        print("")
        return 1

    except (KeyboardInterrupt, dfvfs_errors.UserAbort):
        print("Aborted by user.", file=sys.stderr)
        print("")
        return 1

    if not options.no_hashes:
        logging.info(f"Writing hashes.json to: {target_path:s}")

        hashes_file_path = os.path.join(target_path, "hashes.json")
        with open(hashes_file_path, "w", encoding="utf-8") as file_object:
            json_data = [
                {"sha256": digest, "paths": paths}
                for digest, paths in sorted(relative_paths_by_digest.items())
            ]
            json.dump(json_data, file_object, indent=2)

    if options.artifact_filters and not find_specs_generated:
        print(
            "[ERROR] an extraction filter was specified but no corresponding find "
            "specifications were generated."
        )
        print("")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(Main())
