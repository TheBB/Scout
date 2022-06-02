from functools import partial
import sys

# Setting the Qt bindings for QtPy
import os
os.environ["QT_API"] = "pyside6"

from qtpy.QtWidgets import (
    QAction, QApplication, QFrame, QMainWindow, QVBoxLayout   # type: ignore
)

import numpy as np

import pyvista as pv
from pyvistaqt import MainWindow

from .plotter import ScoutPlotter


class MyMainWindow(MainWindow):

    def __init__(self, parent=None, show=True):
        QMainWindow.__init__(self, parent)

        # create the frame
        self.frame = QFrame()
        vlayout = QVBoxLayout()

        # add the pyvista interactor object
        self.plotter = ScoutPlotter(self.frame)
        vlayout.addWidget(self.plotter.interactor)
        self.signal_close.connect(self.plotter.close)

        self.frame.setLayout(vlayout)
        self.setCentralWidget(self.frame)

        # simple menu to demo functions
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('File')
        exitButton = QAction('Exit', self)
        exitButton.setShortcut('Ctrl+Q')
        exitButton.triggered.connect(self.close)
        fileMenu.addAction(exitButton)

        # allow adding a sphere
        meshMenu = mainMenu.addMenu('Mesh')
        self.add_sphere_action = QAction('Add Sphere', self)
        self.add_sphere_action.triggered.connect(self.add_sphere)
        meshMenu.addAction(self.add_sphere_action)

        self.plotter.set_background('cccccc')
        self.plotter.track_mouse_position()
        self.add_sphere()

        if show:
            self.show()

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


def main():
    print("Welcome to Scout!")
    app = QApplication(sys.argv)
    window = MyMainWindow()
    sys.exit(app.exec_())
