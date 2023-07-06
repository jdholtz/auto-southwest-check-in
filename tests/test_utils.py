import pytest
from pytest_mock import MockerFixture
from requests_mock.mocker import Mocker as RequestMocker

from lib import utils


def test_make_request_raises_exception_on_failure(
    requests_mock: RequestMocker, mocker: MockerFixture
) -> None:
    mock_sleep = mocker.patch("time.sleep")
    requests_mock.post(utils.BASE_URL + "test", status_code=400, reason="error", json={})

    with pytest.raises(utils.RequestError):
        utils.make_request("POST", "test", {}, {}, max_attempts=5)

    assert mock_sleep.call_count == 5


def test_make_request_correctly_posts_data(requests_mock: RequestMocker) -> None:
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


def test_make_request_correctly_gets_data(requests_mock: RequestMocker) -> None:
    mock_post = requests_mock.get(
        utils.BASE_URL + "test", status_code=200, text='{"success": "get"}'
    )

    response = utils.make_request("GET", "test", {"header": "test"}, {"test": "params"})

    assert response == {"success": "get"}

    last_request = mock_post.last_request
    assert last_request.method == "GET"
    assert last_request.url == utils.BASE_URL + "test?test=params"
    assert last_request.headers["header"] == "test"


def test_make_request_handles_malformed_URLs(requests_mock: RequestMocker) -> None:
    mock_post = requests_mock.get(utils.BASE_URL + "test/test2", status_code=200, text="{}")
    utils.make_request("GET", "/test//test2", {}, {})
    assert mock_post.last_request.url == utils.BASE_URL + "test/test2"
