from __future__ import annotations

import os
os.environ['QT_API'] = 'pyside6'

from abc import ABC, abstractmethod
from pathlib import Path

from typing import List, Iterable

from qtpy.QtCore import (
    Qt,         # type: ignore
    QSize,
)

from qtpy.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QLayout,
    QMainWindow,
    QProgressDialog,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from loguru import logger

from splipy.io import G2
from splipy import SplineModel
from splipy.splinemodel import TopologicalNode
import splipy.volume_factory as vf

from ..config import Persistent
from .plotter import ScoutPlotter


class ProblemsPanel(QWidget):

    model: SplineModel

    def __init__(self, model: SplineModel, parent = None):
        super().__init__(parent)
        self.model = model

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(['Problem description'])

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        self.setLayout(layout)

    def _degenerate_at_dim(self, dim: int) -> QTreeWidgetItem:
        items = [
            QTreeWidgetItem([f'Node {hex(id(node))}'])
            for node in self.model.degenerate_nodes(dim)
        ]

        title = {1: 'Edges', 2: 'Surfaces', 3: 'Volumes'}[dim]
        retval = QTreeWidgetItem([f'{title} ({len(items)})'])
        retval.insertChildren(0, items)
        return retval

    def _twins_at_dim(self, dim: int) -> QTreeWidgetItem:
        items = []
        for nodes in self.model.twin_nodes(dim):
            nodestring = ',  '.join(hex(id(node)) for node in nodes)
            items.append(QTreeWidgetItem([f'Nodes {nodestring}']))

        title = {1: 'Edges', 2: 'Surfaces', 3: 'Volumes'}[dim]
        retval = QTreeWidgetItem([f'{title} ({len(items)})'])
        retval.insertChildren(0, items)
        return retval

    def _dimensional_item(self, fun, title):
        items = [fun(1), fun(2), fun(3)]

        nproblems = sum(item.childCount() for item in items)
        retval = QTreeWidgetItem([f'{title} ({nproblems})'])
        retval.insertChildren(0, items)
        return retval

    def refresh(self):
        self.tree.clear()
        self.tree.insertTopLevelItem(0, self._dimensional_item(self._degenerate_at_dim, 'Degenerate nodes'))
        self.tree.insertTopLevelItem(1, self._dimensional_item(self._twins_at_dim, 'Incompatible interfaces'))

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setWidth(400)
        return hint


class OperationsPanel(QWidget):

    main: ScoutMainWindow

    def __init__(self, main: ScoutMainWindow, parent = None):
        super().__init__(parent)

        self.main = main

        layout = QVBoxLayout()

        extrude = QPushButton('Extrude')
        extrude.clicked.connect(self.extrude)
        layout.addWidget(extrude)

        layout.addStretch(1)
        self.setLayout(layout)

    def extrude(self, *args, **kwargs):
        nodes = [
            node for node in self.main.selected_nodes()
            if node.pardim == 2
        ]

        new_objects = [
            vf.extrude(node.obj, amount=(0, 0, 1))
            for node in nodes
        ]

        for obj in new_objects:
            self.main.model.add(obj, raise_on_twins=False)


class ScoutMainWindow(QMainWindow):

    model: SplineModel
    persistent: Persistent

    plotter: ScoutPlotter

    docks: List[QDockWidget]
    problems: ProblemsPanel
    operations: OperationsPanel

    def __init__(self, persistent: Persistent, parent = None):
        QMainWindow.__init__(self, parent)

        self.docks = []
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.VerticalTabs)

        self.persistent = persistent
        self.model = SplineModel(pardim=3, dimension=3)

        self.plotter = ScoutPlotter(self.model, self)
        self.setCentralWidget(self.plotter)

        # Create the potential problems panel
        logger.debug("Initializing Problems")
        self.problems = ProblemsPanel(self.model, self)
        self.make_dock(self.problems, "Potential problems")

        # Create the operations panel
        logger.debug("Initializing Operations")
        self.operations = OperationsPanel(self, self)
        self.make_dock(self.operations, "Operations")

        self.setup_menu()

    def make_dock(self, widget: QWidget, title: str):
        dock = QDockWidget(title)
        dock.setFeatures(
            QDockWidget.DockWidgetClosable |
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable
        )
        dock.setAllowedAreas(
            Qt.LeftDockWidgetArea |
            Qt.RightDockWidgetArea
        )
        dock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.docks.append(dock)

    def finalize(self):
        pass

    def setup_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        open_action = file_menu.addAction("Open")
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)

        view_menu = menu.addMenu("View")

        for dock in self.docks:
            view_menu.addAction(dock.toggleViewAction())

    def open_file(self):
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
                self.model.add(patch, raise_on_twins=False)
            except:
                progress.cancel()
                raise
            progress.setValue(i)

        self.plotter.reset_camera()
        self.problems.refresh()

    def selected_nodes(self) -> Iterable[TopologicalNode]:
        yield from self.plotter.selected_nodes()


def run(persistent, args):
    app = QApplication(args)
    window = ScoutMainWindow(persistent)
    window.show()
    try:
        return app.exec_()
    finally:
        window.finalize()
