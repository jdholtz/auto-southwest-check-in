# Contributing to Auto-Southwest Check-In
Welcome! Thanks for considering contributing to the development of **Auto-Southwest Check-In**. This guide contains useful tips and guidelines
to contribute to this project.

If you plan on making any changes that might not be fully agreed on, it is recommended to open an issue detailing your ideas first.

Submit all changes to the `develop` branch. This allows for separation between new changes and the latest stable release. When submitting a
Pull Request, make sure to add the change/feature to the [Upcoming](CHANGELOG.md#upcoming) section of the Changelog with a reference to the
Pull Request (This can be done after submitting the PR or separately by me).

## Table of Contents
- [Testing](#testing)
- [Coding Conventions](#coding-conventions)
    * [Linting](#linting)
    * [Formatting](#formatting)
    * [Class Method Organization](#class-method-organization)

## Testing
This project uses [pytest][0] to unit test the application. When adding/modifying the code, you may need to add a new test or modify an existing test.

The goal of these tests is to provide 100% code coverage to increase the reliability of existing features and smoothly integrate new ones into the project.
To learn about running unit tests for **Auto-Southwest Check-In**, visit the [Testing README](tests/README.md).

## Coding Conventions
Try to stay consistent with the current layout/format of the project. Please use your best judgement when following the conventions in this guide.

It is highly recommended for you to use [pre-commit][1] to ensure you are following these conventions.

### Linting
[Flake8][2] is used to lint the Python code. When validating your code against flake8, use your best judgement to determine whether to fix
the issue or disable the warning.

[Codespell][3] is used to reduce typos in comments, strings, and documentation.

### Formatting
[Black][4] is used to format all the Python code to a consistent style. Additionally, [isort][5] is used to provide a consistent ordering to imports.

It is also highly recommended to use an [EditorConfig][6] plugin for your code editor to maintain a consistent coding style for all project files.

### Class Method Organization
To help with readability, Auto-Southwest Check-In should follow a specific ordering of class methods:
1. Magic methods (such as \_\_init\_\_)
2. Public methods
3. Private methods (prefixed with an underscore)

From there, methods are ordered from top to bottom in the order they are used. Unit tests should be in the same order as the methods they are testing.


[0]: https://docs.pytest.org
[1]: https://pre-commit.com
[2]: https://flake8.pycqa.org/en/latest
[3]: https://github.com/codespell-project/codespell
[4]: https://black.readthedocs.io/en/stable
[5]: https://pycqa.github.io/isort/
[6]: https://editorconfig.org/
