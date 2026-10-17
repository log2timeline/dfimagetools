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
from dfimagetools import file_entry_filters
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
        description="Extracts data streams from a storage media image."
    )
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
        "--include_duplicates",
        "--include-duplicates",
        dest="include_duplicates",
        action="store_true",
        default=False,
        help=(
            "By default a digest hash (SHA-256) is calculated for each data stream. "
            "These hashes are compared to the previously extracted files and "
            "duplicates are skipped. Use this option to include duplicate files in "
            "the extraction."
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
    filter_group = argument_parser.add_argument_group(
        title="filter",
        description="Options for filtering the data streams to be extracted.",
    )
    filter_group.add_argument(
        "--artifact_filters",
        "--artifact-filters",
        dest="artifact_filters",
        type=str,
        default=None,
        metavar="NAMES",
        action="store",
        help="Comma separated list of names of artifact definitions to extract.",
    )
    filter_group.add_argument(
        "--extension_filter",
        "--extension-filter",
        dest="extension_filter",
        type=str,
        default=None,
        metavar="EXTENSIONS",
        action="store",
        help=(
            "Filter on file name extensions. This option accepts multiple comma "
            'separated values e.g. "csv,docx,pst".'
        ),
    )
    filter_group.add_argument(
        "--name_filter",
        "--name-filter",
        dest="name_filter",
        type=str,
        default=None,
        metavar="NAMES",
        action="store",
        help=(
            "Filter on file names. This option accepts a comma separated "
            'string denoting all file names, e.g. "NTUSER.DAT,UsrClass.dat".'
        ),
    )
    filter_group.add_argument(
        "--path",
        dest="path_filter",
        type=str,
        default=None,
        metavar="PATH",
        action="store",
        help="Path of data stream to extract.",
    )
    filter_group.add_argument(
        "--time_filter",
        "--time-filter",
        dest="time_filters",
        type=str,
        default=[],
        metavar="TIME_START_END",
        action="append",
        help=(
            "Filter based on file entry time ranges. This parameter "
            'is formatted as "TIME_VALUE,START_DATE_TIME,END_DATE_TIME" where '
            "TIME_VALUE defines which file entry timestamp the filter applies "
            "to e.g. atime, ctime, crtime, bkup, etc. START_DATE_TIME and "
            "END_DATE_TIME define respectively the start and end of the "
            "time range. A time range requires at minimum one of the two "
            "timestamps to be set. The date and time values are formatted as: "
            "YYYY-MM-DD hh:mm:ss.######[+-]##:## where # are numeric digits "
            "ranging from 0 to 9 and the seconds fraction can be either 3 "
            "or 6 digits. The time of day, seconds fraction and time zone "
            "offset are optional. The default time zone is UTC. "
            'E.g. "atime, 2013-01-01 23:12:14, 2013-02-23". This parameter '
            "can be repeated as needed to add additional time boundaries, "
            "e.g. once for atime, once for crtime, etc."
        ),
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

    elif not (
        options.path_filter
        or options.name_filter
        or options.extension_filter
        or options.time_filters
    ):
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
    file_entry_filter_collection = file_entry_filters.FileEntryFilterCollection()

    extension_filter = options.extension_filter
    if extension_filter:
        extensions = [
            extension.strip().lower() for extension in extension_filter.split(",")
        ]
        file_entry_filter_collection.AddFilter(
            file_entry_filters.ExtensionsFileEntryFilter(extensions)
        )

    name_filter = options.name_filter
    if name_filter:
        names = [name.strip().lower() for name in name_filter.split(",")]
        file_entry_filter_collection.AddFilter(
            file_entry_filters.NamesFileEntryFilter(names)
        )

    if options.time_filters:
        time_filter = file_entry_filters.DateTimeFileEntryFilter()
        for time_filter_string in options.time_filters:
            time_filter_pieces = time_filter_string.split(",")
            if len(time_filter_pieces) != 3:
                print(
                    f"[ERROR] unsupported time filter: {time_filter_string:s} "
                    "is not formatted as TIME_START_END."
                )
                print("")
                return 1

            time_value, start_time_string, end_time_string = (
                piece.strip() for piece in time_filter_pieces
            )
            try:
                time_filter.AddDateTimeRange(
                    time_value,
                    start_time_string=start_time_string,
                    end_time_string=end_time_string,
                )
            except ValueError as exception:
                print(
                    f"[ERROR] unsupported time filter: {time_filter_string:s} "
                    f"with error: {exception!s}"
                )
                print("")
                return 1

        file_entry_filter_collection.AddFilter(time_filter)

    if file_entry_filter_collection.HasFilters():
        logging.info("File entry filters:")
        for line in file_entry_filter_collection.Describe():
            logging.info(line)

    filter_generator = None

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
            else:
                file_entries_generator = entry_lister.ListFileEntries([base_path_spec])

            stream_writer = data_stream_writer.DataStreamWriter()

            for file_entry, path_segments in file_entries_generator:
                if not file_entry_filter_collection.Matches(file_entry):
                    continue

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
