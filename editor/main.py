import argparse
import sys
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog
from .ui.main_window import MainWindow
from .ui.project_launcher import ProjectLauncher


def main(argv=None,*,settings=None):
    parser = argparse.ArgumentParser(description="Obsidian Studio")
    parser.add_argument("project", nargs="?", help='Preselect a .nen project or legacy project.json in the project manager')
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName("NodeEngine")
    app.setApplicationName("Obsidian Studio")
    settings=settings if settings is not None else QSettings('NodeEngine','ObsidianStudio')
    app.setQuitOnLastWindowClosed(False)
    selected=args.project
    error=''
    while True:
        launcher=ProjectLauncher(settings,initial_project=selected,error=error)
        if launcher.exec()!=QDialog.DialogCode.Accepted:
            return 0
        selected=launcher.project_path
        window=MainWindow(settings=settings)
        if window.open_project(selected):
            window.show()
            app.setQuitOnLastWindowClosed(True)
            return app.exec()
        error=window.console.toPlainText()
        window.dirty=False
        window.close()
        window.deleteLater()


if __name__ == "__main__":
    raise SystemExit(main())
