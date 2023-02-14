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
    * [Formatting](#formatting)

## Testing
This project uses [pytest][0] to unit test the application. When adding/modifying the code, you may need to add a new test or modify an existing test.

The goal of these tests is to provide 100% code coverage to increase the reliability of existing features and smoothly integrate new ones into the project.
To learn about running unit tests for **Auto-Southwest Check-In**, visit the [Testing README](tests/README.md).

## Coding Conventions
Try to stay consistent with the current layout/format of the project. Please use your best judgement when following the conventions in this guide.

It is highly recommended for you to use [pre-commit][1] to ensure you are following these conventions.

### Formatting
[Black][2] is used to format all the Python code to a consistent style. Additionally, [isort][3] is used to provide a consistent ordering to imports.

It is also highly recommended to use an [EditorConfig][4] plugin for your code editor to maintain a consistent coding style for all project files.

[0]: https://docs.pytest.org
[1]: https://pre-commit.com
[2]: https://black.readthedocs.io/en/stable
[3]: https://pycqa.github.io/isort/
[4]: https://editorconfig.org/
