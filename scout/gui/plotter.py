from functools import partial
from itertools import product, chain

import numpy as np
import vtk

import pyvista as pv
import pyvista._vtk as _vtk
from pyvista.utilities import try_callback
from pyvista.utilities.helpers import convert_array
from pyvistaqt import QtInteractor

from splipy import SplineModel
from splipy.splinemodel import TopologicalNode


def subdiv(grid):
    import vtk
    filt = vtk.vtkDataSetSurfaceFilter()
    filt.SetInputDataObject(grid)
    filt.SetNonlinearSubdivisionLevel(2)
    filt.Update()
    ngrid = filt.GetOutputDataObject(0)
    return pv.wrap(ngrid)


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


def bezierize(obj):
    if obj.pardim not in (1, 2):
        return None

    obj.set_dimension(3)

    for direction in range(obj.pardim):
        for kt in obj.knots(direction):
            while obj.bases[direction].continuity(kt) > -1:
                obj.insert_knot(kt, direction)

    lengths = obj.order()
    npts_per_cell = np.prod(lengths)
    ncells = np.prod([n//l for n, l in zip(obj.controlpoints.shape, lengths)])

    points = np.empty((ncells, npts_per_cell, 3))
    weights = np.empty((ncells, npts_per_cell))
    degrees = np.empty((ncells, obj.pardim + 1), dtype=int)
    degrees[:, :-1] = tuple(k-1 for k in obj.order())
    degrees[:, -1] = npts_per_cell
    celltypes = np.empty((ncells,), dtype=np.uint8)
    celltypes[:] = {
        1: vtk.VTK_BEZIER_CURVE,
        2: vtk.VTK_BEZIER_QUADRILATERAL,
    }[obj.pardim]

    cells = np.empty((ncells, npts_per_cell + 1), dtype=int)
    point_id = 0

    roots = [range(0, n, l) for n, l in zip(obj.controlpoints.shape, lengths)]
    for cell_id, root_idx in enumerate(product(*roots)):
        if cell_id >= ncells:
            break
        slice_expr = tuple(slice(r, r+l) for r, l in zip(root_idx, lengths))
        cell_points = obj.controlpoints[(*slice_expr, ...)]
        points[cell_id, ...] = cell_points[..., :3].reshape(-1, 3)
        if obj.rational:
            weights[cell_id, ...] = cell_points[..., 3].reshape(-1)
        else:
            weights[cell_id, ...] = 1
        point_id, cells[cell_id, ...] = cell_enumerate(point_id, *lengths)

    points /= weights[..., np.newaxis]

    mesh = pv.UnstructuredGrid(cells, celltypes, points.reshape(-1,3))
    mesh.point_data.VTKObject.SetRationalWeights(convert_array(weights.reshape(-1)))

    if obj.pardim > 1:
        mesh.cell_data.VTKObject.SetHigherOrderDegrees(convert_array(degrees))

    return mesh


class ScoutPlotter(QtInteractor):

    model: SplineModel

    _successful_pick: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = SplineModel(pardim=3, dimension=3)
        self.model.add_callback('add', self.add_new_node_callback)

        self.iren.interactor.AddObserver('LeftButtonPressEvent', partial(try_callback, self.launch_pick_event))

        point_picker = _vtk.vtkPointPicker()
        point_picker.SetTolerance(0.025)
        point_picker.AddObserver(_vtk.vtkCommand.EndPickEvent, self.point_pick_callback)

        mesh_picker = _vtk.vtkPropPicker()
        mesh_picker.AddObserver(_vtk.vtkCommand.EndPickEvent, self.mesh_pick_callback)

        self.pickers = [
            point_picker,
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
        jobj = subdiv(obj)
        if node.obj.pardim == 1:
            self.add_mesh(jobj, pickable=True, line_width=5, show_edges=True, color='000000')
        else:
            self.add_mesh(jobj, pickable=True)
        # self.add_points(pv.PolyData(obj.points), point_size=20, render_points_as_spheres=True)

    def point_pick_callback(self, picker, event):
        point_id = picker.GetPointId()
        if point_id < 0:
            return
        mesh = picker.GetDataSet()
        # pts = mesh.associated_pts
        # pts.point_data['disp'][pts.prev_id] = 0
        # pts.point_data['disp'][point_id] = 1
        # pts.prev_id = point_id
        self._successful_pick = True

    def mesh_pick_callback(self, picker, event):
        actor = picker.GetActor()
        if not actor:
            return
        mesh = actor.GetMapper().GetInput()
        self._successful_pick = True

    def launch_pick_event(self, interactor, event):
        click_x, click_y = interactor.GetEventPosition()
        renderer = interactor.GetInteractorStyle()._parent()._plotter.renderer

        self._successful_pick = False
        for picker in self.pickers:
            picker.Pick(click_x, click_y, 0, renderer)
            if self._successful_pick:
                return
