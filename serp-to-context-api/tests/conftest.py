import pytest
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

@pytest.fixture
def mock_html_content():
    """Returns the content of the debug.html file."""
    debug_html_path = PROJECT_ROOT / "debug.html"
    if not debug_html_path.exists():
        return "<html><body><h1>Mock Search Result</h1><div class='g'><a href='https://example.com'><h3>Example Domain</h3></a></div></body></html>"
    
    with open(debug_html_path, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def minimal_html_content():
    """Returns a minimal HTML snippet that should pass the parser."""
    return """
    <html>
        <body>
            <div class="g">
                <!-- Anchor & Pivot Logic expects: <a> containing <h3> -->
                <a href="https://example.com/result">
                    <h3>Test Result Title</h3>
                </a>
                <div>
                    This is a snippet for the test result.
                </div>
            </div>
            <div class="g">
                <a href="https://ignore.me/googleadservices">
                    <h3>Ad Result</h3>
                </a>
            </div>
        </body>
    </html>
    """
