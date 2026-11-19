import pytest


@pytest.mark.parametrize("path", [
    "/api/jobs/%2e%2e",
    "/api/jobs/%2e%2e/frame",
    "/api/renders/%2e%2e/file",
    "/api/renders/not-a-real-id",
])
def test_malformed_ids_404(client, path):
    assert client.get(path).status_code == 404
