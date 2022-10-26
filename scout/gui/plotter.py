from functools import partial
from itertools import product, chain

from typing import Dict, Optional, Tuple, List

import numpy as np

from qtpy.QtCore import Qt

import pyvista as pv
import pyvista._vtk as _vtk
from pyvista.utilities import try_callback
from pyvista.utilities.helpers import convert_array
from pyvistaqt import QtInteractor
import pyvistaqt.rwi as rwi

import vtk
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkRenderingCore import vtkPropPicker

from loguru import logger

from splipy import SplineModel
from splipy.splinemodel import TopologicalNode


def _subdivide(order, knots):
    f = [i/(order - 1) for i in range(order - 1)]
    for i, kt in enumerate(knots[:-1]):
        rt = knots[i+1]
        for ff in f:
            yield (1 - ff) * kt + ff * rt
    yield knots[-1]


def subdivide(order, knots):
    if order == 2:
        return knots
    return list(_subdivide(order, knots))


def bezierize(obj):
    if obj.pardim not in (1, 2):
        return None

    obj.set_dimension(3)
    evalpts = [subdivide(order, kts) for order, kts in zip(obj.order(), obj.knots())]
    points = obj(*evalpts)
    mesh = pv.StructuredGrid(points[..., 0], points[..., 1], points[..., 2])
    return mesh


class ScoutPlotter(QtInteractor):

    model: SplineModel

    _nodes: Dict[int, TopologicalNode]
    _picked_actors = List[vtk.vtkOpenGLActor]

    # Set to true by a picking callback when something was found
    _successful_pick: bool = False

    # Set when mouse is clicked to detect movement events upon release
    _mouse_moved: bool = False

    _append_when_picked: bool = False
    _inhibit_release_pick: bool = False

    def __init__(self, model, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._nodes = dict()
        self._picked_actors = []

        self.model = model
        self.model.add_callback('add', self.add_new_node_callback)

        # We also listen to mouse release events, but due to a bug in VTK we have to intercept them earlier
        self._Iren.AddObserver('LeftButtonPressEvent', partial(try_callback, self.left_btn_press))
        self._Iren.AddObserver('KeyPressEvent', partial(try_callback, self.key_press))
        self._Iren.AddObserver('KeyReleaseEvent', partial(try_callback, self.key_release))

        # point_picker = _vtk.vtkPointPicker()
        # point_picker.SetTolerance(0.025)
        # point_picker.AddObserver(_vtk.vtkCommand.EndPickEvent, self.point_pick_callback)

        mesh_picker = vtkPropPicker()
        mesh_picker.AddObserver(vtkCommand.EndPickEvent, self.mesh_pick_callback)

        self.pickers = [
            # point_picker,
            mesh_picker,
        ]

        self.show_axes()
        self.view_xy()
        self.reset_camera()
        self.set_background('cccccc')
        self.track_mouse_position()

    def add_new_node_callback(self, node: TopologicalNode):
        obj = bezierize(node.obj)
        if obj is None:
            return

        if node.obj.pardim == 1:
            actor = self.add_mesh(obj, pickable=True, line_width=5, show_edges=True, color='000000')
        else:
            actor = self.add_mesh(obj, pickable=True)
        self._nodes[actor.GetAddressAsString('')] = node

        self.reset_camera()

    def unpick(self):
        for actor in self._picked_actors:
            address = actor.GetAddressAsString('')
            picked_node = self._nodes[address]
            if picked_node.pardim == 1:
                actor.GetProperty().SetColor(0, 0, 0)
            else:
                actor.GetProperty().SetColor(1, 1, 1)
            self.remove_actor(f'controlpoints-{address}')
        self._picked_actors = []

    def point_pick_callback(self, picker, event):
        return
        point_id = picker.GetPointId()
        if point_id < 0:
            return
        mesh = picker.GetDataSet()
        picker.GetActor().GetProperty().SetColor(0, 0, 0)
        print(picker.GetActor())
        # pts = mesh.associated_pts
        # pts.point_data['disp'][pts.prev_id] = 0
        # pts.point_data['disp'][point_id] = 1
        # pts.prev_id = point_id
        self._successful_pick = True

    def mesh_pick_callback(self, picker, event):
        actor = picker.GetActor()
        if not actor:
            if not self._append_when_picked:
                logger.debug('Failed to find actor - unpicking')
                self.unpick()
            return

        address = actor.GetAddressAsString('')
        node = self._nodes.get(address)
        if not node:
            if not self._append_when_picked:
                logger.debug('Failed to find node - unpicking')
                self.unpick()
            return

        if node.obj.pardim == 1:
            return

        if not self._append_when_picked:
            logger.debug('Picked in non-append mode - unpicking')
            self.unpick()

        cps = node.obj.controlpoints[..., :3].reshape(-1, 3).copy()
        if node.obj.rational:
            cps /= node.obj.controlpoints[..., -1].reshape(-1, 1)

        self.add_points(pv.PolyData(cps), render_points_as_spheres=True, point_size=10, name=f'controlpoints-{address}')
        actor.GetProperty().SetColor(1, 196/255, 87/255)
        self._picked_actors.append(actor)
        self._successful_pick = True

    def do_pick(self, interactor, append: bool = False):
        click_x, click_y = interactor.GetEventPosition()
        renderer = interactor.GetInteractorStyle()._parent()._plotter.renderer

        self._append_when_picked = append
        self._successful_pick = False
        for picker in self.pickers:
            picker.Pick(click_x, click_y, 0, renderer)
            if self._successful_pick:
                break

        self._append_when_picked = False

    def left_btn_press(self, interactor, event):
        self._mouse_moved = False
        if interactor.GetControlKey():
            logger.debug('Launch append-pick')
            self.do_pick(self._Iren, append=True)
            self._inhibit_release_pick = True

    def key_press(self, interactor, event):
        # print('press', interactor.GetControlKey(), interactor.GetShiftKey(), interactor.GetKeyCode(), interactor.GetKeySym())
        pass

    def key_release(self, interactor, event):
        # print('release', interactor.GetControlKey(), interactor.GetShiftKey(), interactor.GetKeyCode(), interactor.GetKeySym())
        pass

    def mouseReleaseEvent(self, ev):
        retval = super().mouseReleaseEvent(ev)
        if self._ActiveButton == Qt.MouseButton.LeftButton and not self._mouse_moved and not self._inhibit_release_pick:
            logger.debug('Launch normal pick')
            self.do_pick(self._Iren)
        self._inhibit_release_pick = False
        return retval

    def mouseMoveEvent(self, ev):
        self._mouse_moved = True
        return super().mouseMoveEvent(ev)
