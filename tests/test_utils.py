import pytest
import requests_mock
from pytest_mock import MockerFixture

from lib import utils


def test_make_request_raises_exception_on_failure(
    requests_mock: requests_mock.mocker.Mocker, mocker: MockerFixture
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    requests_mock.post(utils.BASE_URL + "test", status_code=400, reason="error")

    with pytest.raises(utils.RequestError):
        utils.make_request("POST", "test", {}, {}, max_attempts=5)

    assert mock_sleep.call_count == 5


def test_make_request_correctly_posts_data(requests_mock: requests_mock.mocker.Mocker) -> None:
    mock_post = requests_mock.post(
        utils.BASE_URL + "test", status_code=200, text='{"success": "post"}'
    )

    response = utils.make_request("POST", "test", {"header": "test"}, {"test": "json"})

    assert response == {"success": "post"}

    last_request = mock_post.last_request
    assert last_request.method == "POST"
    assert last_request.url == utils.BASE_URL + "test"
    assert last_request.headers["header"] == "test"
    assert last_request.json() == {"test": "json"}


def test_make_request_correctly_gets_data(requests_mock: requests_mock.mocker.Mocker) -> None:
    mock_post = requests_mock.get(
        utils.BASE_URL + "test", status_code=200, text='{"success": "get"}'
    )

    response = utils.make_request("GET", "test", {"header": "test"}, {"test": "params"})

    assert response == {"success": "get"}

    last_request = mock_post.last_request
    assert last_request.method == "GET"
    assert last_request.url == utils.BASE_URL + "test?test=params"
    assert last_request.headers["header"] == "test"
