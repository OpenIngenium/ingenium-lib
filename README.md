# ingenium-lib

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Libraries and scripts to interact with and support [Ingenium](https://github.com/OpenIngenium) operations. This repository provides the `ing_lib` Python package and a set of command-line utilities for managing Ingenium project configurations, venues, test step data, and AMPCS dictionaries.

## Structure

The repository is organized as follows:

-   `ing_lib/`: The main Python package.
    -   `__init__.py`: Package initializer and version (`0.1.0`) accessor.
    -   `common.py`: Shared utility functions, REST helpers, authentication handling, Ingenium API endpoint constants, and the `IngeniumLibError` exception.
    -   `logs.py`: Logging configuration using `RichHandler` for console output.
    -   `project_config.py`: Core library for querying and managing Ingenium Project Configurations, including command/telemetry dictionaries, V&V information, and custom scripts.
    -   `venue.py`: Client library for the Ingenium venue management API, including venue and venue group operations.
    -   `steps.py`: Helper classes and functions for creating Ingenium steps, including bit-mask operations and `ReturnOn` enums.
    -   `apps/`: Command-line applications for managing Project Configurations:
        -   `ProjConfigBackup.py`: Backs up project configuration content from an Ingenium server.
        -   `ProjConfigRestore.py`: Restores project configuration content from a backup file.
        -   `ProjConfigClear.py`: Deletes all project configuration information from an Ingenium server.
        -   `ProjConfigCreateUpdateCS.py`: Creates or updates a custom script on an Ingenium server from XML or JSON input.
        -   `ProjConfigLoadDict.py`: Reads XML dictionary files (AMPCS or XTCE format) and uploads them to an Ingenium server.
        -   `ProjConfigPalette.py`: Reads/writes the Step Palette to an Excel file and supports query, diff, and update modes.
    -   `utils/`: Standalone utility scripts.
        -   `ProjConfigV3toV4Convert.py`: Converts verification item (VI) JSON data from API v3 format to v4 format.
    -   `tests/`: Pytest test suite, including unit and integration tests for the library and all applications.
-   `setup.py`: Installation configuration for the `ing_lib` package.
-   `requirements.txt`: Python package dependencies.
-   `LICENSE`: Apache 2.0 license.

## Related repositories

Reference steps and schemas live in [ingenium-ref](https://github.com/OpenIngenium/ingenium-ref):

-   `docs/custom_script_schema.rnc`: RELAX NG Compact schema for custom script XML, the format read by `ProjConfigCreateUpdateCS.py` and `ProjConfigPalette.py`.
-   `steps/reference/`: Example steps built on `ing_lib`, each with sample input/output JSON and a `custom_script.xml`.

## Installation

To install the `ing_lib` package and its runtime/test dependencies, run:

```bash
pip install -r requirements.txt
pip install .
```

This will install the package and its dependencies (e.g., `rich`). The package requires Python 3.10 or higher.
