"""Keep one QApplication alive across all editor test modules on Windows."""
import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session')
def app():
    # All editor modules share the same application lifetime.
    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    yield application
    for widget in application.topLevelWidgets():
        widget.deleteLater()
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


@pytest.fixture(autouse=True)
def pump_gui_events(request):
    """Drain Windows/Qt notifications between tests that use the editor."""
    if 'app' not in request.fixturenames:
        yield
        return
    application = request.getfixturevalue('app')
    application.processEvents()
    yield
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
