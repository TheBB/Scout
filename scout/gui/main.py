from pathlib import Path
import os

os.environ["QT_API"] = "pyside6"

from qtpy.QtCore import Qt      # type: ignore

from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pyvistaqt import MainWindow
from splipy.io import G2

from .plotter import ScoutPlotter
from .widgets import Collapsible
from ..config import Persistent


class ProblemsPanel(Collapsible):

    def __init__(self, parent):
        super().__init__('Potential problems', parent)

        layout = QVBoxLayout()
        layout.addWidget(QPushButton())
        self.set_content_layout(layout)


class OperationsPanel(Collapsible):

    def __init__(self, parent):
        super().__init__('Operations', parent)

        layout = QVBoxLayout()
        layout.addWidget(QPushButton())
        self.set_content_layout(layout)


class ToolPanel(QWidget):

    def __init__(self, parent):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        problems = ProblemsPanel(self)
        layout.addWidget(problems)

        operations = OperationsPanel(self)
        layout.addWidget(operations)

        layout.insertStretch(-1, 1)
        self.setLayout(layout)


class ScoutMainWindow(MainWindow):

    persistent: Persistent
    plotter: ScoutPlotter

    def __init__(self, persistent: Persistent, parent=None):
        QMainWindow.__init__(self, parent)

        self.persistent = persistent

        # Create the frame
        self.splitter = QSplitter(Qt.Horizontal, self)

        # Add the pyvista interactor object
        self.plotter = ScoutPlotter(self)
        self.splitter.addWidget(self.plotter.interactor)
        self.signal_close.connect(self.plotter.close)

        # Add the right hand side tool panel
        self.splitter.addWidget(ToolPanel(self))

        self.splitter.setSizes([persistent.main_splitter_left, persistent.main_splitter_right])
        self.setCentralWidget(self.splitter)

        # Set up the rest of the GUI
        self.setup_menu()

    def finalize(self):
        sizes = self.splitter.sizes()
        self.persistent.main_splitter_left = sizes[0]
        self.persistent.main_splitter_right = sizes[1]

    def setup_menu(self):
        """Create the menu bar"""
        menu = self.menuBar()

        file_menu = menu.addMenu('File')

        open_action = file_menu.addAction('Open')
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)

        file_menu.addSeparator()

        exit_action = file_menu.addAction('Exit')
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)

    def open_file(self):
        """Callback for the 'Open' menu item."""
        path, selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open File",
            self.persistent.open_file_path,
            "G2 files (*.g2)",
            self.persistent.open_file_filter,
        )

        if not path:
            return

        path = Path(path)
        self.persistent.open_file_path = str(path.parent)
        self.persistent.open_file_filter = selected_filter

        with G2(str(path)) as g2:
            patches = g2.read()

        progress = QProgressDialog(
            "Adding patches...",
            "Cancel",
            0, len(patches),
            self,
        )
        progress.setWindowModality(Qt.WindowModal)

        for i, patch in enumerate(patches, start=1):
            if progress.wasCanceled():
                break
            try:
                self.plotter.add_new_patch(patch)
            except:
                progress.cancel()
                raise
            progress.setValue(i)

        self.plotter.reset_camera()


def run(persistent, args):
    app = QApplication(args)
    window = ScoutMainWindow(persistent)
    window.show()
    try:
        return app.exec_()
    finally:
        window.finalize()
