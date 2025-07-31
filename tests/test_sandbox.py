# Copyright(c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for the OneMCP sandbox service."""

from fastapi.testclient import TestClient

from onemcp.sandboxing.__main__ import app


class TestSandboxService:
    """Test the sandbox FastAPI service."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_root_endpoint(self):
        """Test the health check endpoint."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["service"] == "OneMCP Sandbox"

    def test_discover_endpoint(self):
        """Test the discover endpoint."""
        request_data = {"repository_url": "https://example.com/repo.git"}
        response = self.client.post("/discover", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["response_code"] == "SUCCESS"
        assert "overview" in data
        assert "tools" in data
        assert "bootstrap_metadata" in data

    def test_start_endpoint(self):
        """Test the start endpoint."""
        request_data = {
            "bootstrap_metadata": {
                "version": "1.0.0",
                "config": {"test_param": "test_value"}
            }
        }
        response = self.client.post("/start", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["response_code"] == "SUCCESS"
        assert "sandbox_id" in data
        assert "endpoint" in data

    def test_stop_endpoint(self):
        """Test the stop endpoint."""
        # First start a sandbox
        start_request = {
            "bootstrap_metadata": {
                "version": "1.0.0",
                "config": {"test_param": "test_value"}
            }
        }
        start_response = self.client.post("/start", json=start_request)
        sandbox_id = start_response.json()["sandbox_id"]

        # Then stop it
        stop_request = {"sandbox_id": sandbox_id}
        response = self.client.post("/stop", json=stop_request)
        assert response.status_code == 200

        data = response.json()
        assert data["response_code"] == "SUCCESS"

    def test_stop_nonexistent_sandbox(self):
        """Test stopping a non-existent sandbox returns error."""
        request_data = {"sandbox_id": "nonexistent-id"}
        response = self.client.post("/stop", json=request_data)
        assert response.status_code == 200  # MockSandbox returns 200 with error in body

        data = response.json()
        assert data["response_code"] == "ERROR"
        assert "error_description" in data


class TestLifespanPattern:
    """Test that the service uses modern lifespan patterns."""

    def test_no_deprecated_on_event_usage(self):
        """Verify the code doesn't use deprecated @app.on_event patterns."""
        import inspect

        from onemcp.sandboxing import __main__ as sandbox_main

        # Get the source code of the module
        source = inspect.getsource(sandbox_main)

        # Check that deprecated patterns are not used (exclude comments)
        lines = [line.strip() for line in source.split('\n') if not line.strip().startswith('#') and not line.strip().startswith('"""')]
        code_content = '\n'.join(lines)

        assert "@app.on_event" not in code_content, "Found deprecated @app.on_event usage in code"

        # Check that modern lifespan pattern is used
        assert "lifespan" in source, "Modern lifespan pattern not found"
        assert "@asynccontextmanager" in source, "Lifespan context manager not found"

    def test_lifespan_function_exists(self):
        """Test that the lifespan function is properly defined."""
        from onemcp.sandboxing.__main__ import lifespan

        assert callable(lifespan), "Lifespan should be callable"

        # Check that it's a context manager (asynccontextmanager decorated function)
        assert hasattr(lifespan, '__wrapped__'), "Lifespan should be a decorated function"
