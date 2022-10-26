from __future__ import annotations

import os
os.environ['QT_API'] = 'pyside6'

from abc import ABC, abstractmethod
from pathlib import Path

from typing import List

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

from ..config import Persistent
from .plotter import ScoutPlotter


def point_as_string(pt):
    nums = ', '.join(f'{s:.2g}' for s in pt)
    return f'({nums})'


class Problem(ABC):

    nodes: List[TopologicalNode]

    @abstractmethod
    def short_desc(self) -> str:
        pass

    @abstractmethod
    def long_desc(self) -> str:
        pass

    def layout(self) -> QLayout:
        label = QLabel()
        label.setText(str(self))
        layout = QVBoxLayout()
        layout.addWidget(label)
        return layout


class DegenerateProblem(Problem):

    def __init__(self, node):
        self.nodes = [node]

    def short_desc(self):
        node = self.nodes[0]
        if node.pardim == 1:
            return 'Degenerate edge'
        if node.pardim == 2:
            return 'Degenerate face'
        assert node.pardim == 3
        return 'Degenerate volume'

    def long_desc(self):
        node = self.nodes[0]
        corners = [point_as_string(c) for c in node.obj.corners()]
        if node.pardim == 1:
            return f'Edge from {corners[0]} to {corners[1]} is degenerate'
        if node.pardim == 2:
            cstr = ', '.join(str(c) for c in corners[:-1])
            return f'Face joining {cstr} and {corners[-1]} is degenerate'
        assert node.pardim == 3
        cstr = ', '.join(str(c) for c in corners[:-1])
        return f'Volume joining {cstr}, and {corners[-1]} is degenerate'


class TwinProblem(Problem):

    def __init__(self, nodes):
        self.nodes = nodes

    def short_desc(self):
        if self.nodes[0].pardim == 1:
            return f'Incompatible edges ({len(self.nodes)})'
        if self.nodes[0].pardim == 2:
            return f'Incompatible faces ({len(self.nodes)})'
        assert self.nodes[0].pardim == 3
        return f'Incompatible volumes ({len(self.nodes)})'

    def long_desc(self):
        if self.nodes[0].pardim == 1:
            return f'{len(self.nodes)} edges appear coincident but are incompatible'
        if self.nodes[0].pardim == 2:
            return f'{len(self.nodes)} faces appear coincident but are incompatible'
        assert self.nodes[0].pardim == 3
        return f'{len(self.nodes)} volumes appear coincident but are incompatible'


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
        layout.addStretch(1)
        self.setLayout(layout)

    def make_problems(self) -> List[Problem]:
        problems = []
        for pardim in range(1, 4):
            for node in self.model.degenerate_nodes(pardim):
                problems.append(DegenerateProblem(node))
            for cls in self.model.twin_nodes(pardim):
                problems.append(TwinProblem(list(cls)))
        return problems

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

    def __init__(self, model: SplineModel, parent = None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.addWidget(QPushButton('Extrude'))
        layout.addStretch(1)
        self.setLayout(layout)


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
        self.operations = OperationsPanel(self.model, self)
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


def run(persistent, args):
    app = QApplication(args)
    window = ScoutMainWindow(persistent)
    window.show()
    try:
        return app.exec_()
    finally:
        window.finalize()
