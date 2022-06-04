from pathlib import Path
import os

os.environ["QT_API"] = "pyside6"
from qtpy.QtWidgets import (
    QAction,                    # type: ignore
    QApplication,
    QFileDialog,
    QFrame,
    QMainWindow,
    QVBoxLayout,
)

import numpy as np

import pyvista as pv
from pyvistaqt import MainWindow

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

        # Add a mesh
        self.add_sphere()

    def setup_menu(self):
        """Create the menu bar"""
        menu = self.menuBar()

        file_menu = menu.addMenu('File')

        open_action = file_menu.addAction('Open')
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)

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

    def add_sphere(self):
        """ add a sphere to the pyqt frame """

        points = np.array([
            (0, 0, 0),
            (1, 0, 0),
            (0.5, 0.667, 0),
        ])

        cells = np.array([
            [3, 0, 1, 2]
        ])

        mesh = pv.PolyData(points, cells)
        pts = pv.PolyData(points)
        pts.point_data['disp'] = [0, 0, 0]
        pts.prev_id = 0
        mesh.associated_pts = pts

        self.plotter.add_mesh(mesh, pickable=True, show_edges=True, line_width=5)
        self.plotter.add_points(pts, pickable=False, point_size=50, render_points_as_spheres=True, show_scalar_bar=False)
        self.plotter.show_axes()
        self.plotter.view_xy()
        self.plotter.reset_camera()
        self.plotter.set_background('cccccc')
        self.plotter.track_mouse_position()


def run(persistent, args):
    app = QApplication(args)
    window = ScoutMainWindow(persistent)
    window.show()
    return app.exec_()
