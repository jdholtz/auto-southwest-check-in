# Unit Testing
The following guide covers how to run all unit tests for auto-southwest-check-in

## Running Tests
[Pytest][0] is used to run all unit tests. Unit tests are automatically run after every push
using a [GitHub workflow][1].

### Setup
Install all the requirements needed
```shell
$ pip install -r tests/requirements.txt
```

### Running The Tests
To run all tests
```shell
$ pytest
```

To run all tests for a specific module
```shell
$ pytest tests/test_<module name>.py
```
Or multiple
```shell
$ pytest tests/test_<module1>.py tests/test_<module2>.py
```

To get a coverage report
```shell
$ pytest --cov
```

[0]: https://docs.pytest.org/en/7.1.x/index.html
[1]: ../.github/workflows/tests.yml
