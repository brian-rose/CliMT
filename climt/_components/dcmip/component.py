from ..._core import ClimtDiagnostic
import numpy as np

try:
    from . import _dcmip
except ImportError:
    print('Import Failed. DCMIP initial conditions will not be available!')


class DcmipInitialConditions(ClimtDiagnostic):
    """
        Climt interface to the DCMIP initial conditions.
        Currently only provides interfaces to tests 4 and 5.
    """

    _climt_inputs = {
        'latitude': 'degrees_north',
        'longitude': 'degrees_east',
        'air_pressure': 'Pa',
    }

    _climt_diagnostics = {
        'eastward_wind': 'm s^-1',
        'northward_wind': 'm s^-1',
        'air_temperature': 'degK',
        'surface_geopotential': 'm^2 s^-2',
        'surface_air_pressure': 'Pa'
    }

    quantity_descriptions = {
        'latitude': {
            'dims': ['y'],
            'units': 'degrees_north',
            'default_value': 0.
        },
        'longitude': {
            'dims': ['x'],
            'units': 'degrees_east',
            'default_value': 0.
        },
    }

    def __init__(self, type_of_output='baroclinic_wave'):
        """
        Initialise the DCMIP module.

        Args:

            type_of_output (optional, str):
                The type of initial conditions desired. Can be
                one of :code:`'baroclinic_wave'` or
                :code:`'tropical_cyclone'`

        """

        # TODO Implement full DCMIP ICs

        if type_of_output not in ['baroclinic_wave', 'tropical_cyclone']:
            raise ValueError("type_of_output has to be one \
                             of 'baroclinic_wave' or 'tropical_cyclone'")

        self._output = type_of_output

        if type_of_output == 'tropical_cyclone':
            self._climt_diagnostics['specific_humidity'] = 'g/g'

    def __call__(self, state):
        """
        Get initial conditions for DCMIP tests.

        Args:
            state (dict):
                State dictionary. Should contain 'air_pressure',
                'latitude' and 'longitude' defined.

        Returns:
            diagnostics(dict):
                The desired initial conditions.
        """

        raw_arrays = self.get_numpy_arrays_from_state('_climt_inputs', state)
        if len(raw_arrays['latitude'].shape) == 1:  # 1D coordinate

            latitude, longitude = np.meshgrid(np.radians(raw_arrays['latitude']),
                                              np.radians(raw_arrays['longitude']))

            longitude = np.asfortranarray(longitude)
            latitude = np.asfortranarray(latitude)
        else:

            longitude = np.radians(raw_arrays['longitude'])
            latitude = np.radians(raw_arrays['latitude'])

        diag = self.create_state_dict_for('_climt_diagnostics', state)
        if self._output is 'baroclinic_wave':
            u, v, t, ps, phis = _dcmip.get_baroclinic_wave_ics(raw_arrays['air_pressure'],
                                                               longitude, latitude)

            diag['eastward_wind'].values[:] = u
            diag['northward_wind'].values[:] = v
            diag['air_temperature'].values[:] = t
            diag['surface_geopotential'].values[:] = phis
            diag['surface_air_pressure'].values[:] = ps

            return diag

        elif self._output is 'tropical_cyclone':
            u, v, t, q, ps, phis = _dcmip.get_tropical_cyclone_ics(raw_arrays['air_pressure'],
                                                                   longitude, latitude)
            diag['eastward_wind'].values[:] = u
            diag['northward_wind'].values[:] = v
            diag['air_temperature'].values[:] = t
            diag['surface_geopotential'].values[:] = phis
            diag['specific_humidity'].values[:] = q
            diag['surface_air_pressure'].values[:] = ps

            return diag
