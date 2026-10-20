import logging


def test_http_client_request_logs_are_silenced_so_api_keys_never_reach_logs():
    # httpx logs "HTTP Request: GET <url>" at INFO; TomTom URLs carry the API key.
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpcore").isEnabledFor(logging.INFO)
