from typing import Any, Dict
from unittest import mock

import pytest
from pytest_mock import MockerFixture
from seleniumwire.request import Request, Response

from lib.account import Account
from lib.webdriver import WebDriver, USER_AGENT

# This needs to be accessed to be tested
# pylint: disable=protected-access


@pytest.fixture(autouse = True)
def mock_driver(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch("lib.webdriver.Chrome")


def test_get_info_gets_checkin_info_when_no_account_is_provided(
    mocker: MockerFixture
) -> None:
    mocker.patch.object(WebDriver, "_get_checkin_info", return_value = "Check In info")

    info = WebDriver().get_info()
    assert info == "Check In info"


def test_get_info_gets_account_info_when_an_account_is_provided(
    mocker: MockerFixture
) -> None:
    mocker.patch.object(WebDriver, "_get_account_info", return_value = "Account info")
    mocker.patch("lib.webdriver.Chrome")

    info = WebDriver().get_info(Account())
    assert info == "Account info"


def test_get_checkin_info_returns_request_headers(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch("time.sleep")
    mocker.patch.object(WebDriver, "_get_needed_headers", return_value = "test_headers")

    headers = WebDriver()._get_checkin_info(mock_driver)
    assert headers == "test_headers"


def test_get_account_info_sets_account_name_when_it_is_not_set(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch("time.sleep")
    mocker.patch.object(WebDriver, "_get_needed_headers", return_value = "test_headers")
    mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")

    request_one = Request(method = "GET", url = "", headers = {})
    request_one.response = Response(status_code = 200, reason = "", headers = {})
    request_one.response.body = '{"name": "John Doe"}'

    request_two = Request(method = "GET", url = "", headers = {})
    request_two.response = Response(status_code = 200, reason = "", headers = {})
    request_two.response.body = '{"upcomingTripsPage": "new flights"}'

    mock_driver.requests = [request_one, request_two]

    account = Account()
    flights = WebDriver()._get_account_info(account, mock_driver)

    assert account.headers == "test_headers"
    mock_set_account_name.assert_called_once_with(account, {"name": "John Doe"})
    assert flights == "new flights"


def test_get_account_info_does_not_set_account_name_when_it_is_already_set(
    mocker: MockerFixture, mock_driver: mock.Mock
) -> None:
    mocker.patch("lib.webdriver.WebDriverWait")
    mocker.patch("time.sleep")
    mocker.patch.object(WebDriver, "_get_needed_headers", return_value = "test_headers")
    mock_set_account_name = mocker.patch.object(WebDriver, "_set_account_name")

    request_one = Request(method = "GET", url = "", headers = {})

    request_two = Request(method = "GET", url = "", headers = {})
    request_two.response = Response(status_code = 200, reason = "", headers = {})
    request_two.response.body = '{"upcomingTripsPage": "new flights"}'

    mock_driver.requests = [request_one, request_two]

    account = Account()
    account.first_name = "John"
    flights = WebDriver()._get_account_info(account, mock_driver)

    assert account.headers == "test_headers"
    mock_set_account_name.assert_not_called()
    assert flights == "new flights"


def test_get_options_adds_the_necessary_options() -> None:
    options = WebDriver._get_options()

    assert "--headless" in options.arguments
    assert "--user-agent=" + USER_AGENT in options.arguments


@pytest.mark.parametrize(
    ["original_headers", "expected_headers"],
    [
        ({"unneccesary": "header"}, {}),
        ({"X-API-Key": "API Key"}, {"X-API-Key": "API Key"}),
        ({"X-Channel-ID": "ID"}, {"X-Channel-ID": "ID"}),
        ({"User-Agent": "Chrome"}, {"User-Agent": "Chrome"}),
        ({"EE30zvQLWf-b": "secret"}, {"EE30zvQLWf-b": "secret"}),
    ],
)
def test_get_needed_headers_returns_matching_headers(
    original_headers: Dict[str, Any], expected_headers: Dict[str, Any]
) -> None:
    headers = WebDriver._get_needed_headers(original_headers)
    assert headers == expected_headers


def test_set_account_name_sets_the_correct_values_for_the_name() -> None:
    account = Account()
    WebDriver._set_account_name(account, {"customers.userInformation.firstName": "John",
                                          "customers.userInformation.lastName": "Doe"})

    assert account.first_name == "John"
    assert account.last_name == "Doe"
