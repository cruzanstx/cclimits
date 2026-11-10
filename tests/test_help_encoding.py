"""--help must render on non-UTF-8 consoles (e.g. Windows cp1252)."""

import io
from unittest.mock import patch

import pytest

from cclimits import main


class TestHelpEncoding:
    def test_help_on_cp1252_stdout(self):
        buf = io.BytesIO()
        wrapper = io.TextIOWrapper(buf, encoding="cp1252")
        with (
            patch("sys.argv", ["cclimits", "--help"]),
            patch("sys.stdout", wrapper),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 0
        wrapper.flush()
        text = buf.getvalue().decode("cp1252")
        assert "usage" in text.lower()
        assert "--resets" in text
