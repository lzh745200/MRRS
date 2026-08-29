import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_db_context(mock_db):
    cm = MagicMock()
    cm.__enter__.return_value = mock_db
    cm.__exit__.return_value = None
    return cm


class TestSchedulerFunctionsExist:

    def test_scheduler_state_variables(self):
        from app.services.backup_scheduler import _scheduler_started, _timers
        assert isinstance(_scheduler_started, bool)
        assert isinstance(_timers, list)














