from typing import List

import pytest
from pytest_mock import MockerFixture

import southwest


def test_print_version_prints_script_version(capsys: pytest.CaptureFixture[str]) -> None:
    southwest.print_version()
    assert southwest.__version__ in capsys.readouterr().out


def test_print_usage_prints_script_usage(capsys: pytest.CaptureFixture[str]) -> None:
    southwest.print_usage()
    output = capsys.readouterr().out
    assert southwest.__version__ in output
    assert southwest.__doc__ in output


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_check_flags_prints_version_when_version_flag_is_passed(
    mocker: MockerFixture,
    flag: str,
) -> None:
    mock_print_version = mocker.patch("southwest.print_version")

    with pytest.raises(SystemExit):
        southwest.check_flags([flag])

    mock_print_version.assert_called_once()


@pytest.mark.parametrize("arguments", [["-h"], ["--help"]])
def test_check_flags_prints_usage_when_help_flag_is_passed(
    mocker: MockerFixture,
    arguments: List[str],
) -> None:
    mock_print_usage = mocker.patch("southwest.print_usage")

    with pytest.raises(SystemExit):
        southwest.check_flags(arguments)

    mock_print_usage.assert_called_once()


def test_check_flags_does_not_exit_when_flags_are_not_matched(
    mocker: MockerFixture,
) -> None:
    mock_exit = mocker.patch("sys.exit")
    southwest.check_flags(["--invalid-flag"])
    mock_exit.assert_not_called()


def test_init_sets_up_the_script(mocker: MockerFixture) -> None:
    mock_check_flags = mocker.patch("southwest.check_flags")
    mock_main = mocker.patch("lib.main.main")
    arguments = ["test", "arguments", "--verbose", "-v"]

    southwest.init(arguments)
    mock_check_flags.assert_called_once_with(arguments)

    mock_main.assert_called_once_with(arguments, southwest.__version__)
