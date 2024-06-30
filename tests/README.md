# Automated Testing
The following guide covers how to run all tests for auto-southwest-check-in. There are two types
of tests currently implemented: unit tests and integration tests.

## Writing Tests
Writing automated tests for new features or bug fixes is vital to maintaining the reliability of
auto-southwest-check-in. Unit tests should be written/modified when any code changes enough to
trigger test failures or when that code isn't tested (can be seen with a coverage report).

Integration tests should be added whenever a large feature is added or changed. These tests should
test multiple parts of the script rather than just one.

The test naming and formatting conventions can be replicated from the tests that already exist.

## Running Tests
[Pytest] is used to run all tests. Both unit tests and integration tests are automatically run
after every pull request and push to the `master` branch using a [GitHub workflow]. Additionally,
unit tests are also run on every push to the `develop` branch.

### Setup
Install all the requirements needed
```shell
pip install -r tests/requirements.txt
```

### Running The Tests
To run all tests
```shell
pytest
```

To run only unit tests
```shell
pytest tests/unit
```

To run only integration tests
```shell
pytest tests/integration
```

To run all tests for a specific module
```shell
pytest tests/unit/test_<module name>.py
```
Or multiple
```shell
pytest tests/unit/test_<module1>.py tests/unit/test_<module2>.py
```

To get a coverage report
```shell
pytest --cov
```

[Pytest]: https://docs.pytest.org
[GitHub workflow]: ../.github/workflows/tests.yml
