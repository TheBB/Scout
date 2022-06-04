from functools import partial

import pyvista._vtk as _vtk
from pyvista.utilities import try_callback
from pyvistaqt import QtInteractor


class ScoutPlotter(QtInteractor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

        self._successful_pick = False

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
