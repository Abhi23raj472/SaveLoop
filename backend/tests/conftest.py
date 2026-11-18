import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client():
    main.extract_limiter.reset()
    main.download_limiter.reset()
    return TestClient(main.app)
