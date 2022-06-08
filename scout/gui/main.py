from pathlib import Path
import os

os.environ["QT_API"] = "pyside6"

from qtpy.QtCore import Qt      # type: ignore

from qtpy.QtWidgets import (
    QAction,                    # type: ignore
    QApplication,
    QFileDialog,
    QFrame,
    QMainWindow,
    QProgressDialog,
    QVBoxLayout,
)

import numpy as np

import pyvista as pv
from pyvistaqt import MainWindow
from splipy.io import G2

from .plotter import ScoutPlotter
from ..config import Persistent


class ScoutMainWindow(MainWindow):

    persistent: Persistent
    plotter: ScoutPlotter

    def __init__(self, persistent: Persistent, parent=None):
        QMainWindow.__init__(self, parent)

        self.persistent = persistent

        # create the frame
        frame = QFrame(self)
        vlayout = QVBoxLayout()

        # add the pyvista interactor object
        self.plotter = ScoutPlotter(frame)
        vlayout.addWidget(self.plotter.interactor)
        self.signal_close.connect(self.plotter.close)

        frame.setLayout(vlayout)
        self.setCentralWidget(frame)

        # Set up the rest of the GUI
        self.setup_menu()

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
    return app.exec_()
