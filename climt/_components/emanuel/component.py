from ..._core import ClimtImplicitPrognostic, bolton_q_sat
from sympl import replace_none_with_default
import numpy as np
import _emanuel_convection


class EmanuelConvection(ClimtImplicitPrognostic):
    """
    The Emanuel convection scheme from `[Emanuel and Živković-Rothman]`_

    .. _[Emanuel and Živković-Rothman]:
        http://journals.ametsoc.org/doi/abs/10.1175/1520-0469(1999)056%3C1766%3ADAEOAC%3E2.0.CO%3B2

    """

    # TODO: Add additional tracers
    _climt_inputs = {
        'air_temperature': 'degK',
        'specific_humidity': 'g/g',
        'saturation_specific_humidity': 'g/g',
        'eastward_wind': 'm s^-1',
        'northward_wind': 'm s^-1',
        'air_pressure': 'mbar',
        'air_pressure_on_interface_levels': 'mbar',
        'atmosphere_convective_mass_flux': 'kg m^-2 s^-1',
    }

    _climt_diagnostics = {
        'convective_state': 'dimensionless',
        'convective_precipitation_rate': 'mm day^-1',
        'convective_downdraft_velocity_scale': 'm s^-1',
        'convective_downdraft_temperature_scale': 'degK',
        'convective_downdraft_specific_humidity_scale': 'g/g',
        'atmosphere_convective_mass_flux': 'kg m^-2 s^-1',
        'atmosphere_convective_available_potential_energy': 'J kg^-1'
    }

    _climt_tendencies = {
        'air_temperature': 'degK s^-1',
        'specific_humidity': 'g g^-1 s^-1',
    }

    def __init__(self,
                 simulate_boundary_layer=0,
                 minimum_convecting_layer=1,
                 autoconversion_water_content_threshold=0.0011,
                 autoconversion_temperature_threshold=-55,
                 entrainment_mixing_coefficient=1.5,
                 downdraft_area_fraction=0.05,
                 precipitation_fraction_outside_cloud=0.12,
                 speed_water_droplets=50.0,
                 speed_snow=5.5,
                 rain_evaporation_coefficient=1.0,
                 snow_evaporation_coefficient=0.8,
                 convective_momentum_transfer_coefficient=0.7,
                 downdraft_surface_velocity_coefficient=10.0,
                 convection_bouyancy_threshold=0.9,
                 mass_flux_relaxation_rate=0.1,
                 mass_flux_damping_rate=0.1,
                 reference_mass_flux_timescale=300.,
                 number_of_tracers=0,
                 specific_heat_dry_air=None,
                 specific_heat_condensible=None,
                 specific_enthalpy_condensible=2500.,
                 gas_constant_condensible=None,
                 gas_constant_dry_air=None,
                 latent_heat_condensation=None,
                 acceleration_gravity=None,
                 density_condensed_phase=1000.):
        """

        Args:

            simulate_boundary_layer (int, optional):
                Whether the scheme must perform dry adiabatic adjustment near the surface.
                This will modify the input fields **in place**. Do not use if your model
                includes a separate boundary layer scheme.

            minimum_convecting_layer (int, optional):
                The least model level from which convection can be initiated. Normally set
                to :code:`1` if using bulk PBL schemes. Else, it should be set to the first
                model level at which the temperature is defined.

            autoconversion_water_content_threshold (float, optional):
                The amount of water vapour in :math:`kg/kg`
                above which condensation occurs in warm (above freezing point of water)
                clouds. This value linearly reduces to zero between the freezing point and
                the :code:`autoconversion_temperature_threshold`.

            autoconversion_temperature_threshold (float, optional):
                The temperature in :math:`^\circ C` below which
                all water vapour is converted to rain/snow.

            entrainment_mixing_coefficient (float, optional):
                The coefficient of mixing for entrainment of environmental air into
                the cloud.

            downdraft_area_fraction (float, optional):
                The fractional area covered by unsaturated downdrafts.

            precipitation_fraction_outside_cloud (float, optional):
                The fraction of precipitation falling outside the cloud.

            speed_water_droplets (float, optional):
                The speed of descent of water droplets in :math:`Pa/s`.

            speed_snow (float, optional):
                The speed of descent of snow in :math:`Pa/s`.

            rain_evaporation_coefficient (float, optional):
                Coefficient governing the rate of evaporation of rain.

            snow_evaporation_coefficient (float, optional):
                Coefficient governing the rate of evaporation of snow.

            convective_momentum_transfer_coefficient (float, optional):
                Coefficient **between 0 and 1** governing momentum transport
                by clouds.

            downdraft_surface_velocity_coefficient (float, optional):
                Coefficient mulitplying the downdraft mass flux to calculate
                the downdraft velocity scale.

            convection_bouyancy_threshold (float, optional):
                The maximum negative temperature perturbation in :math:`degK` a parcel can
                have below the temperature at its level of free convection.
                If difference is greater, and previous cloud base mass flux
                is zero, there is no convection.

            mass_flux_relaxation_rate (float, optional):
                Coefficient governing the rate of relaxation to subcloud-layer
                quasi-equilibrium.

            mass_flux_damping_rate (float, optional):
                Coefficient which damps the currently calculated mass flux towards
                the value from the previous time step.

            reference_mass_flux_timescale (float, optional):
                Timescale used to calculate the actual damping coefficient along with
                :code:`mass_flux_damping_rate` and the current time step.

            number_of_tracers (integer, optional):
                The number of additional tracers advected by the code.

            specific_heat_dry_air (float, optional):
                The heat capacity of dry air in :math:`J kg^{-1} K^{-1}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            specific_heat_condensible (float, optional):
                The heat capacity of the condensible substance in :math:`J kg^{-1} K^{-1}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            specific_enthalpy_condensible (float, optional):
                The specific enthalpy of the condensible substance in :math:`J kg^{-1} K^{-1}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            gas_constant_condensible (float, optional):
                The gas constant for the condensible substance in :math:`J kg^{-1} K^{-1}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            gas_constant_dry_air (float, optional):
                The gas constant for dry air in :math:`J kg^{-1} K^{-1}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            latent_heat_condensation (float, optional):
                The latent heat of condensation for the condensible substance in
                :math:`J kg^{-1}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            acceleration_gravity (float, optional):
                The acceleration due to gravity in :math:`m s^{-2}`.
                If None, the default value in :code:`sympl.default_constants` is used.

            density_condensed_phase (float, optional):
                The density in the condensed phase of the condensible substance in
                :math:`kg m^{-3}`.
                If None, the default value in :code:`sympl.default_constants` is used.
        """

        if (convective_momentum_transfer_coefficient < 0 or
                convective_momentum_transfer_coefficient > 1):
            raise ValueError("Momentum transfer coefficient must be between 0 and 1.")

        if (downdraft_area_fraction < 0 or
                downdraft_area_fraction > 1):
            raise ValueError("Downdraft fraction must be between 0 and 1.")

        if (precipitation_fraction_outside_cloud < 0 or
                precipitation_fraction_outside_cloud > 1):
            raise ValueError("Outside cloud precipitation fraction must be between 0 and 1.")

        if number_of_tracers != 0:
            raise NotImplementedError("Component does not yet support additional tracers")

        self._con_mom_txfr = convective_momentum_transfer_coefficient
        self._downdraft_area_frac = downdraft_area_fraction
        self._precip_frac_outside_cloud = precipitation_fraction_outside_cloud

        self._pbl = simulate_boundary_layer
        self._min_conv_layer = minimum_convecting_layer
        self._crit_humidity = autoconversion_water_content_threshold
        self._crit_temp = autoconversion_temperature_threshold
        self._entrain_coeff = entrainment_mixing_coefficient
        self._droplet_speed = speed_water_droplets
        self._snow_speed = speed_snow
        self._rain_evap = rain_evaporation_coefficient
        self._snow_evap = snow_evaporation_coefficient
        self._beta = downdraft_surface_velocity_coefficient
        self._dtmax = convection_bouyancy_threshold
        self._mf_damp = mass_flux_damping_rate
        self._alpha = mass_flux_relaxation_rate
        self._mf_timescale = reference_mass_flux_timescale
        self._ntracers = number_of_tracers

        self._g = replace_none_with_default(
            'gravitational_acceleration', acceleration_gravity)

        self._Cpd = replace_none_with_default(
            'heat_capacity_of_dry_air_at_constant_pressure',
            specific_heat_dry_air)

        self._Cpv = replace_none_with_default(
            'heat_capacity_of_dry_air_at_constant_pressure',
            specific_heat_condensible)

        self._Rair = replace_none_with_default(
            'gas_constant_of_dry_air',
            gas_constant_dry_air)

        self._Rcond = replace_none_with_default(
            'gas_constant_of_water_vapor',
            gas_constant_condensible)

        self._Lv = replace_none_with_default(
            'latent_heat_of_vaporization_of_water',
            latent_heat_condensation)

        self._rho_condensible = replace_none_with_default(
            'density_of_liquid_water',
            density_condensed_phase)

        self._Cl = replace_none_with_default(
            'specific_enthalpy_water_vapor',
            specific_enthalpy_condensible)

        _emanuel_convection.init_emanuel_convection(
            self._pbl, self._min_conv_layer,
            self._crit_humidity,
            self._crit_temp, self._entrain_coeff,
            self._downdraft_area_frac,
            self._precip_frac_outside_cloud,
            self._droplet_speed, self._snow_speed,
            self._rain_evap, self._snow_evap,
            self._con_mom_txfr, self._dtmax,
            self._beta, self._alpha, self._mf_damp,
            self._Cpd, self._Cpv, self._Cl,
            self._Rcond, self._Rair,
            self._Lv, self._g,
            self._rho_condensible, self._mf_timescale)

    def __call__(self, state):
        """
        Get convective heating and moistening.

        Args:

            state (dict):
                The state dictionary

        Returns:

            tendencies (dict), diagnostics (dict):
                * The heating and moistening tendencies
                * Any diagnostics associated.

        """

        raw_arrays = self.get_numpy_arrays_from_state('_climt_inputs', state)

        num_lons, num_cols, num_levs = raw_arrays['air_temperature'].shape

        max_conv_level = num_levs - 3

        tend_dict = self.create_state_dict_for('_climt_tendencies', state)
        diag_dict = self.create_state_dict_for('_climt_diagnostics', state)

        # TODO this should happen at the array handling level itself
        diag_dict['convective_state'].values = np.array(
            diag_dict['convective_state'].shape, dtype=np.int32_t, order='F')

        q_sat = np.asfortranarray(bolton_q_sat(
            raw_arrays['air_temperature'],
            raw_arrays['air_pressure'],
            self._Cpd, self._Cpv))

        tend_arrays = self.get_numpy_arrays_from_state('_climt_tendencies', tend_dict)
        diag_arrays = self.get_numpy_arrays_from_state('_climt_diagnostics', diag_dict)

        for lon in range(num_lons):

            _emanuel_convection.convect(
                num_levs,
                num_cols,
                max_conv_level,
                self._ntracers,
                self.current_time_step,
                raw_arrays['air_temperature'][lon, :],
                raw_arrays['specific_humidity'][lon, :],
                q_sat[lon, :],
                raw_arrays['eastward_wind'][lon, :],
                raw_arrays['northward_wind'][lon, :],
                raw_arrays['air_pressure'][lon, :],
                raw_arrays['air_pressure_on_interface_levels'][lon, :],
                diag_arrays['convective_state'][lon, :],
                diag_arrays['convective_precipitation_rate'][lon, :],
                diag_arrays['convective_downdraft_velocity_scale'][lon, :],
                diag_arrays['convective_downdraft_temperature_scale'][lon, :],
                diag_arrays['convective_downdraft_specific_humidity_scale'][lon, :],
                raw_arrays['atmosphere_convective_mass_flux'][lon, :],
                diag_arrays['atmosphere_convective_available_potential_energy'][lon, :],
                tend_arrays['air_temperature'][lon, :],
                tend_arrays['specific_humidity'][lon, :],
                tend_arrays['eastward_wind'][lon, :],
                tend_arrays['northward_wind'][lon, :],
            )

            return tend_dict, diag_dict
