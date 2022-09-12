from functools import partial
from itertools import product, chain
from typing import Dict, Optional

import numpy as np
import vtk

import pyvista as pv
import pyvista._vtk as _vtk
from pyvista.utilities import try_callback
from pyvista.utilities.helpers import convert_array
from pyvistaqt import QtInteractor

from splipy import SplineModel
from splipy.splinemodel import TopologicalNode


def cell_enumerate(start, *npts):
    if len(npts) == 1:
        nx, = npts
        retval = np.array([nx, 0, nx - 1, *range(1, nx - 1)], dtype=int)
    elif len(npts) == 2:
        nx, ny = npts
        umax = (nx - 1) * ny
        vmax = ny - 1
        uvmax = nx * ny - 1
        retval = np.array([
            nx * ny,
            0, umax, uvmax, vmax,
            *range(0, umax, ny)[1:],
            *range(umax, uvmax)[1:],
            *range(vmax, uvmax, ny)[1:],
            *range(0, vmax)[1:],
            *chain.from_iterable(
                range(k, umax + k, ny)[1:]
                for k in range(0, vmax)[1:]
            ),
        ])
    else:
        raise ValueError(len(npts))
    retval[1:] += start
    return start + retval[0], retval


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

    _successful_pick: bool = False
    _picked_actor: Optional[vtk.vtkOpenGLActor] = None

    _nodes: Dict[int, TopologicalNode]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nodes = dict()

        self.model = SplineModel(pardim=3, dimension=3)
        self.model.add_callback('add', self.add_new_node_callback)

        self.iren.interactor.AddObserver('LeftButtonPressEvent', partial(try_callback, self.launch_pick_event))

        # point_picker = _vtk.vtkPointPicker()
        # point_picker.SetTolerance(0.025)
        # point_picker.AddObserver(_vtk.vtkCommand.EndPickEvent, self.point_pick_callback)

        mesh_picker = _vtk.vtkPropPicker()
        mesh_picker.AddObserver(_vtk.vtkCommand.EndPickEvent, self.mesh_pick_callback)

        self.pickers = [
            # point_picker,
            mesh_picker,
        ]

        self.show_axes()
        self.view_xy()
        self.reset_camera()
        self.set_background('cccccc')
        self.track_mouse_position()

    def add_new_patch(self, patch):
        """Callback for the open file menu item."""
        self.model.add(patch, raise_on_twins=False)

    def add_new_node_callback(self, node: TopologicalNode):
        """Callback for when a new node is added to the model."""
        obj = bezierize(node.obj)
        if obj is None:
            return

        if node.obj.pardim == 1:
            actor = self.add_mesh(obj, pickable=True, line_width=5, show_edges=True, color='000000')
        else:
            actor = self.add_mesh(obj, pickable=True)
        self._nodes[actor.GetAddressAsString('')] = node

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

    def unpick(self):
        if self._picked_actor:
            picked_node = self._nodes[self._picked_actor.GetAddressAsString('')]
            if picked_node.pardim == 1:
                self._picked_actor.GetProperty().SetColor(0, 0, 0)
            else:
                self._picked_actor.GetProperty().SetColor(1, 1, 1)
        self.remove_actor('controlpoints')

    def mesh_pick_callback(self, picker, event):
        actor = picker.GetActor()
        if not actor:
            self.unpick()
            return

        node = self._nodes.get(actor.GetAddressAsString(''))
        if not node:
            self.unpick()
            return

        if node.obj.pardim == 1:
            return

        self.unpick()

        cps = node.obj.controlpoints[..., :3].reshape(-1, 3).copy()
        if node.obj.rational:
            cps /= node.obj.controlpoints[..., -1].reshape(-1, 1)

        self.add_points(pv.PolyData(cps), render_points_as_spheres=True, point_size=10, name='controlpoints')
        actor.GetProperty().SetColor(1, 196/255, 87/255)
        self._picked_actor = actor
        self._successful_pick = True

    def launch_pick_event(self, interactor, event):
        click_x, click_y = interactor.GetEventPosition()
        renderer = interactor.GetInteractorStyle()._parent()._plotter.renderer

        self._successful_pick = False
        for picker in self.pickers:
            picker.Pick(click_x, click_y, 0, renderer)
            if self._successful_pick:
                return
