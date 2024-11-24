import os
import pytest
from pathlib import Path
from contextlib import contextmanager

@contextmanager
def temp_env_var(key: str, value: str):
    """Context manager to temporarily set an environment variable."""
    original_value = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if original_value is None:
            del os.environ[key]
        else:
            os.environ[key] = original_value


def create_test_config(path: Path, content: str = 'PT_SOCKET = "Hello world"'):
    """Create a temporary test config file."""
    path.write_text(content)
    return path


class TestPathTrackerConfig:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path):
        """Setup and teardown for each test."""
        self.test_dir = tmp_path
        self.config_file = self.test_dir / "testconfig.py"

        # Setup: Create test config
        create_test_config(self.config_file)

        yield

        # Teardown: Clean up test file
        if self.config_file.exists():
            self.config_file.unlink()

    def test_config_loading(self):
        """Test that configuration loads correctly and has expected value."""
        with temp_env_var('PATHTRACKER_CONFIG', str(self.config_file)):
            from pathtracker import config
            assert config.PT_SOCKET == "Hello world"