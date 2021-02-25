##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018-2020, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes-pse".
##############################################################################
"""
Initial property package for seawater system
"""

# Import Python libraries
import idaes.logger as idaeslog

# Import Pyomo libraries
from pyomo.environ import Constraint, Expression, Reals, NonNegativeReals, \
    Var, Param, Suffix, value
from pyomo.environ import units as pyunits

# Import IDAES cores
from idaes.core import (declare_process_block_class,
                        MaterialFlowBasis,
                        PhysicalParameterBlock,
                        StateBlockData,
                        StateBlock,
                        MaterialBalanceType,
                        EnergyBalanceType)
from idaes.core.components import Component, Solute, Solvent
from idaes.core.phases import LiquidPhase
from idaes.core.util.constants import Constants
from idaes.core.util.initialization import (fix_state_vars,
                                            revert_state_vars,
                                            solve_indexed_blocks)
from idaes.core.util.testing import get_default_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.exceptions import PropertyPackageError
import idaes.core.util.scaling as iscale

# Set up logger
_log = idaeslog.getLogger(__name__)


@declare_process_block_class("SeawaterParameterBlock")
class SeawaterParameterData(PhysicalParameterBlock):
    """Parameter block for a seawater property package."""
    CONFIG = PhysicalParameterBlock.CONFIG()

    def build(self):
        '''
        Callable method for Block construction.
        '''
        super(SeawaterParameterData, self).build()

        self._state_block_class = SeawaterStateBlock

        # components
        self.H2O = Solvent()
        self.TDS = Solute()

        # phases
        self.Liq = LiquidPhase()

        # reference
        # this package is developed from Sharqawy et al. (2010) http://dx.doi.org/10.5004/dwt.2010.1079

        # parameters
        # molecular weight
        mw_comp_data = {'H2O': 18.01528E-3,
                        'TDS': 58.44E-3}  # TODO: Confirm how Sharqawy converts TDS to moles
        self.mw_comp = Param(self.component_list,
                             mutable=False,
                             initialize=mw_comp_data,
                             units=pyunits.kg/pyunits.mol,
                             doc="Molecular weight")

        # mass density parameters, eq. 8 in Sharqawy
        self.dens_mass_param_A1 = Var(
            within=Reals, initialize=9.999e2, units=pyunits.kg/pyunits.m**3,
            doc='Mass density parameter A1')
        self.dens_mass_param_A2 = Var(
            within=Reals, initialize=2.034e-2, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-1,
            doc='Mass density parameter A2')
        self.dens_mass_param_A3 = Var(
            within=Reals, initialize=-6.162e-3, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-2,
            doc='Mass density parameter A3')
        self.dens_mass_param_A4 = Var(
            within=Reals, initialize=2.261e-5, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-3,
            doc='Mass density parameter A4')
        self.dens_mass_param_A5 = Var(
            within=Reals, initialize=-4.657e-8, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-4,
            doc='Mass density parameter A5')
        self.dens_mass_param_B1 = Var(
            within=Reals, initialize=8.020e2, units=pyunits.kg/pyunits.m ** 3,
            doc='Mass density parameter B1')
        self.dens_mass_param_B2 = Var(
            within=Reals, initialize=-2.001, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-1,
            doc='Mass density parameter B2')
        self.dens_mass_param_B3 = Var(
            within=Reals, initialize=1.677e-2, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-2,
            doc='Mass density parameter B3')
        self.dens_mass_param_B4 = Var(
            within=Reals, initialize=-3.060e-5, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-3,
            doc='Mass density parameter B4')
        self.dens_mass_param_B5 = Var(
            within=Reals, initialize=-1.613e-5, units=(pyunits.kg/pyunits.m**3) * pyunits.K**-2,
            doc='Mass density parameter B5')

        # dynamic viscosity parameters, eq. 22 and 23 in Sharqawy
        self.visc_d_param_muw_A = Var(
            within=Reals, initialize=4.2844e-5, units=pyunits.Pa*pyunits.s,
            doc='Dynamic viscosity parameter A for pure water')
        self.visc_d_param_muw_B = Var(
            within=Reals, initialize=0.157, units=pyunits.degK**-2*pyunits.Pa**-1*pyunits.s**-1,
            doc='Dynamic viscosity parameter B for pure water')
        self.visc_d_param_muw_C = Var(
            within=Reals, initialize=64.993, units=pyunits.K,
            doc='Dynamic viscosity parameter C for pure water')
        self.visc_d_param_muw_D = Var(
            within=Reals, initialize=91.296, units=pyunits.Pa**-1*pyunits.s**-1,
            doc='Dynamic viscosity parameter D for pure water')
        self.visc_d_param_A_1 = Var(
            within=Reals, initialize=1.541, units=pyunits.dimensionless,
            doc='Dynamic viscosity parameter 1 for term A')
        self.visc_d_param_A_2 = Var(
            within=Reals, initialize=1.998e-2, units=pyunits.K**-1,
            doc='Dynamic viscosity parameter 2 for term A')
        self.visc_d_param_A_3 = Var(
            within=Reals, initialize=-9.52e-5, units=pyunits.K**-2,
            doc='Dynamic viscosity parameter 3 for term A')
        self.visc_d_param_B_1 = Var(
            within=Reals, initialize=7.974, units=pyunits.dimensionless,
            doc='Dynamic viscosity parameter 1 for term B')
        self.visc_d_param_B_2 = Var(
            within=Reals, initialize=-7.561e-2, units=pyunits.K**-1,
            doc='Dynamic viscosity parameter 2 for term B')
        self.visc_d_param_B_3 = Var(
            within=Reals, initialize=4.724e-4, units=pyunits.K**-2,
            doc='Dynamic viscosity parameter 3 for term B')

        # osmotic coefficient parameters, eq. 49 in Sharqawy
        self.osm_coeff_param_1 = Var(
            within=Reals, initialize=8.9453e-1, units=pyunits.dimensionless,
            doc='Osmotic coefficient parameter 1')
        self.osm_coeff_param_2 = Var(
            within=Reals, initialize=4.1561e-4, units=pyunits.K**-1,
            doc='Osmotic coefficient parameter 2')
        self.osm_coeff_param_3 = Var(
            within=Reals, initialize=-4.6262e-6, units=pyunits.K**-2,
            doc='Osmotic coefficient parameter 3')
        self.osm_coeff_param_4 = Var(
            within=Reals, initialize=2.2211e-11, units=pyunits.K**-4,
            doc='Osmotic coefficient parameter 4')
        self.osm_coeff_param_5 = Var(
            within=Reals, initialize=-1.1445e-1, units=pyunits.dimensionless,
            doc='Osmotic coefficient parameter 5')
        self.osm_coeff_param_6 = Var(
            within=Reals, initialize=-1.4783e-3, units=pyunits.K**-1,
            doc='Osmotic coefficient parameter 6')
        self.osm_coeff_param_7 = Var(
            within=Reals, initialize=-1.3526e-8, units=pyunits.K**-3,
            doc='Osmotic coefficient parameter 7')
        self.osm_coeff_param_8 = Var(
            within=Reals, initialize=7.0132, units=pyunits.dimensionless,
            doc='Osmotic coefficient parameter 8')
        self.osm_coeff_param_9 = Var(
            within=Reals, initialize=5.696e-2, units=pyunits.K**-1,
            doc='Osmotic coefficient parameter 9')
        self.osm_coeff_param_10 = Var(
            within=Reals, initialize=-2.8624e-4, units=pyunits.K**-2,
            doc='Osmotic coefficient parameter 10')

        # specific enthalpy parameters, eq. 55 and 43 in Sharqawy
        self.enth_mass_param_A1 = Var(
            within=Reals, initialize=124.790, units=pyunits.J/pyunits.kg,
            doc='Specific enthalpy parameter A1')
        self.enth_mass_param_A2 = Var(
            within=Reals, initialize=4203.075, units=(pyunits.J/pyunits.kg) * pyunits.K**-1,
            doc='Specific enthalpy parameter A2')
        self.enth_mass_param_A3 = Var(
            within=Reals, initialize=-0.552, units=(pyunits.J/pyunits.kg) * pyunits.K**-2,
            doc='Specific enthalpy parameter A3')
        self.enth_mass_param_A4 = Var(
            within=Reals, initialize=0.004, units=(pyunits.J/pyunits.kg) * pyunits.K**-3,
            doc='Specific enthalpy parameter A4')
        self.enth_mass_param_B1 = Var(
            within=Reals, initialize=27062.623, units=pyunits.dimensionless,
            doc='Specific enthalpy parameter B1')
        self.enth_mass_param_B2 = Var(
            within=Reals, initialize=4835.675, units=pyunits.dimensionless,
            doc='Specific enthalpy parameter B2')

        # traditional parameters are the only Vars currently on the block and should be fixed
        for v in self.component_objects(Var):
            v.fix()

        # ---default scaling---
        self.set_default_scaling('temperature', 1e-2)
        self.set_default_scaling('pressure', 1e-6)
        self.set_default_scaling('dens_mass_phase', 1e-3, index='Liq')
        self.set_default_scaling('visc_d_phase', 1e3, index='Liq')
        self.set_default_scaling('osm_coeff', 1e0)
        self.set_default_scaling('enth_mass_phase', 1e-5, index='Liq')

    @classmethod
    def define_metadata(cls, obj):
        """Define properties supported and units."""
        obj.add_properties(
            {'flow_mass_phase_comp': {'method': None},
             'temperature': {'method': None},
             'pressure': {'method': None},
             'mass_frac_phase_comp': {'method': '_mass_frac_phase_comp'},
             'dens_mass_phase': {'method': '_dens_mass_phase'},
             'flow_vol_phase': {'method': '_flow_vol_phase'},
             'flow_vol': {'method': '_flow_vol'},
             'conc_mass_phase_comp': {'method': '_conc_mass_phase_comp'},
             'flow_mol_phase_comp': {'method': '_flow_mol_phase_comp'},
             'mole_frac_phase_comp': {'method': '_mole_frac_phase_comp'},
             'molality_comp': {'method': '_molality_comp'},
             'visc_d_phase': {'method': '_visc_d_phase'},
             'osm_coeff': {'method': '_osm_coeff'},
             'pressure_osm': {'method': '_pressure_osm'},
             'enth_mass_phase': {'method': '_enth_mass_phase'},
             'enth_flow': {'method': '_enth_flow'}
             })

        obj.add_default_units({'time': pyunits.s,
                               'length': pyunits.m,
                               'mass': pyunits.kg,
                               'amount': pyunits.mol,
                               'temperature': pyunits.K})


class _SeawaterStateBlock(StateBlock):
    """
    This Class contains methods which should be applied to Property Blocks as a
    whole, rather than individual elements of indexed Property Blocks.
    """

    def initialize(self, state_args={}, state_vars_fixed=False,
                   hold_state=False, outlvl=idaeslog.NOTSET,
                   solver=None, optarg={}):
        """
        Initialization routine for property package.
        Keyword Arguments:
            state_args : Dictionary with initial guesses for the state vars
                         chosen. Note that if this method is triggered
                         through the control volume, and if initial guesses
                         were not provided at the unit model level, the
                         control volume passes the inlet values as initial
                         guess.The keys for the state_args dictionary are:

                         flow_mass_phase_comp : value at which to initialize
                                               phase component flows
                         pressure : value at which to initialize pressure
                         temperature : value at which to initialize temperature
            outlvl : sets output level of initialization routine
            optarg : solver options dictionary object (default={})
            state_vars_fixed: Flag to denote if state vars have already been
                              fixed.
                              - True - states have already been fixed by the
                                       control volume 1D. Control volume 0D
                                       does not fix the state vars, so will
                                       be False if this state block is used
                                       with 0D blocks.
                             - False - states have not been fixed. The state
                                       block will deal with fixing/unfixing.
            solver : Solver object to use during initialization if None is provided
                     it will use the default solver for IDAES (default = None)
            hold_state : flag indicating whether the initialization routine
                         should unfix any state variables fixed during
                         initialization (default=False).
                         - True - states variables are not unfixed, and
                                 a dict of returned containing flags for
                                 which states were fixed during
                                 initialization.
                        - False - state variables are unfixed after
                                 initialization by calling the
                                 release_state method
        Returns:
            If hold_states is True, returns a dict containing flags for
            which states were fixed during initialization.
        """
        # Get loggers
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        solve_log = idaeslog.getSolveLogger(self.name, outlvl, tag="properties")

        # Set solver and options
        if solver is None:
            opt = get_default_solver()
        else:
            opt = solver
            opt.options = optarg

        # Fix state variables
        flags = fix_state_vars(self, state_args)
        # Check when the state vars are fixed already result in dof 0
        for k in self.keys():
            dof = degrees_of_freedom(self[k])
            if dof != 0:
                raise PropertyPackageError("State vars fixed but degrees of "
                                           "freedom for state block is not "
                                           "zero during initialization.")

        # ---------------------------------------------------------------------
        # Initialize properties
        with idaeslog.solver_log(solve_log, idaeslog.DEBUG) as slc:
            results = solve_indexed_blocks(opt, [self], tee=slc.tee)
        init_log.info("Property initialization: {}."
                      .format(idaeslog.condition(results)))

        # ---------------------------------------------------------------------
        # If input block, return flags, else release state
        if state_vars_fixed is False:
            if hold_state is True:
                return flags
            else:
                self.release_state(flags)

    def release_state(self, flags, outlvl=idaeslog.NOTSET):
        '''
        Method to relase state variables fixed during initialisation.

        Keyword Arguments:
            flags : dict containing information of which state variables
                    were fixed during initialization, and should now be
                    unfixed. This dict is returned by initialize if
                    hold_state=True.
            outlvl : sets output level of of logging
        '''
        # Unfix state variables
        init_log = idaeslog.getInitLogger(self.name, outlvl, tag="properties")
        revert_state_vars(self, flags)
        init_log.info('{} State Released.'.format(self.name))

@declare_process_block_class("SeawaterStateBlock",
                             block_class=_SeawaterStateBlock)
class SeawaterStateBlockData(StateBlockData):
    """A seawater property package."""
    def build(self):
        """Callable method for Block construction."""
        super().build()

        self.scaling_factor = Suffix(direction=Suffix.EXPORT)

        # Add state variables
        self.flow_mass_phase_comp = Var(
            self.params.phase_list,
            self.params.component_list,
            initialize=1,
            bounds=(1e-8, 100),
            domain=NonNegativeReals,
            units=pyunits.kg/pyunits.s,
            doc='Mass flow rate')

        self.temperature = Var(
            initialize=298.15,
            bounds=(273.15, 1000),
            domain=NonNegativeReals,
            units=pyunits.K,
            doc='Temperature')

        self.pressure = Var(
            initialize=101325,
            bounds=(1e5, 5e7),
            domain=NonNegativeReals,
            units=pyunits.Pa,
            doc='Pressure')

    # -----------------------------------------------------------------------------
    # Property Methods
    def _mass_frac_phase_comp(self):
        self.mass_frac_phase_comp = Var(
            self.params.phase_list,
            self.params.component_list,
            initialize=0.1,
            bounds=(1e-8, 1),
            units=pyunits.dimensionless,
            doc='Mass fraction')

        def rule_mass_frac_phase_comp(b, j):
            return (b.mass_frac_phase_comp['Liq', j] == b.flow_mass_phase_comp['Liq', j] /
                    sum(b.flow_mass_phase_comp['Liq', j]
                        for j in self.params.component_list))
        self.eq_mass_frac_phase_comp = Constraint(self.params.component_list, rule=rule_mass_frac_phase_comp)

    def _dens_mass_phase(self):
        self.dens_mass_phase = Var(
            self.params.phase_list,
            initialize=1e3,
            bounds=(1, 1e6),
            units=pyunits.kg * pyunits.m**-3,
            doc="Mass density")

        def rule_dens_mass_phase(b):  # density, eq. 8 in Sharqawy
            t = b.temperature - 273.15 * pyunits.K
            s = b.mass_frac_phase_comp['Liq', 'TDS']
            dens_mass = (b.params.dens_mass_param_A1
                         + b.params.dens_mass_param_A2 * t
                         + b.params.dens_mass_param_A3 * t ** 2
                         + b.params.dens_mass_param_A4 * t ** 3
                         + b.params.dens_mass_param_A5 * t ** 4
                         + b.params.dens_mass_param_B1 * s
                         + b.params.dens_mass_param_B2 * s * t
                         + b.params.dens_mass_param_B3 * s * t ** 2
                         + b.params.dens_mass_param_B4 * s * t ** 3
                         + b.params.dens_mass_param_B5 * s ** 2 * t ** 2)
            return b.dens_mass_phase['Liq'] == dens_mass
        self.eq_dens_mass_phase = Constraint(rule=rule_dens_mass_phase)

    def _flow_vol_phase(self):
        self.flow_vol_phase = Var(
            self.params.phase_list,
            initialize=1,
            bounds=(1e-8, 1e8),
            units=pyunits.m**3 / pyunits.s,
            doc="Volumetric flow rate")

        def rule_flow_vol_phase(b):
            return (b.flow_vol_phase['Liq']
                    == sum(b.flow_mass_phase_comp['Liq', j] for j in self.params.component_list)
                    / b.dens_mass_phase['Liq'])
        self.eq_flow_vol_phase = Constraint(rule=rule_flow_vol_phase)

    def _flow_vol(self):

        def rule_flow_vol(b):
            return sum(b.flow_vol_phase[p] for p in self.params.phase_list)
        self.flow_vol = Expression(rule=rule_flow_vol)

    def _conc_mass_phase_comp(self):
        self.conc_mass_phase_comp = Var(
            self.params.phase_list,
            self.params.component_list,
            initialize=10,
            bounds=(1e-6, 1e6),
            units=pyunits.kg * pyunits.m**-3,
            doc="Mass concentration")

        def rule_conc_mass_phase_comp(b, j):
            return (self.conc_mass_phase_comp['Liq', j] ==
                    self.dens_mass_phase['Liq'] * self.mass_frac_phase_comp['Liq', j])
        self.eq_conc_mass_phase_comp = Constraint(self.params.component_list, rule=rule_conc_mass_phase_comp)

    def _flow_mol_phase_comp(self):
        self.flow_mol_phase_comp = Var(
            self.params.phase_list,
            self.params.component_list,
            initialize=100,
            bounds=(1e-6, 1e6),
            units=pyunits.mol / pyunits.s,
            doc="Molar flowrate")

        def rule_flow_mol_phase_comp(b, j):
            return (b.flow_mol_phase_comp['Liq', j] ==
                    b.flow_mass_phase_comp['Liq', j] / b.params.mw_comp[j])
        self.eq_flow_mol_phase_comp = Constraint(self.params.component_list, rule=rule_flow_mol_phase_comp)

    def _mole_frac_phase_comp(self):
        self.mole_frac_phase_comp = Var(
            self.params.phase_list,
            self.params.component_list,
            initialize=0.1,
            bounds=(1e-8, 1),
            units=pyunits.dimensionless,
            doc="Mole fraction")

        def rule_mole_frac_phase_comp(b, j):
            return (b.mole_frac_phase_comp['Liq', j] == b.flow_mol_phase_comp['Liq', j] /
                    sum(b.flow_mol_phase_comp['Liq', j] for j in b.params.component_list))
        self.eq_mole_frac_phase_comp = Constraint(self.params.component_list, rule=rule_mole_frac_phase_comp)

    def _molality_comp(self):
        self.molality_comp = Var(
            ['TDS'],
            initialize=1,
            bounds=(1e-6, 1e6),
            units=pyunits.mole / pyunits.kg,
            doc="Molality")

        def rule_molality_comp(b, j):
            return (self.molality_comp[j] ==
                    b.mass_frac_phase_comp['Liq', j]
                    / (1 - b.mass_frac_phase_comp['Liq', j])
                    / b.params.mw_comp[j])
        self.eq_molality_comp = Constraint(['TDS'], rule=rule_molality_comp)

    def _visc_d_phase(self):
        self.visc_d_phase = Var(
            self.params.phase_list,
            initialize=1e-3,
            bounds=(1e-8, 1),
            units=pyunits.Pa * pyunits.s,
            doc="Viscosity")

        def rule_visc_d_phase(b):  # dynamic viscosity, eq. 22 and 23 in Sharqawy
            t = b.temperature - 273.15 * pyunits.K  # temperature in degC, but pyunits are K
            s = b.mass_frac_phase_comp['Liq', 'TDS']
            mu_w = (b.params.visc_d_param_muw_A
                    + (b.params.visc_d_param_muw_B *
                       (t + b.params.visc_d_param_muw_C) ** 2
                       - b.params.visc_d_param_muw_D) ** -1)
            A = (b.params.visc_d_param_A_1
                 + b.params.visc_d_param_A_2 * t
                 + b.params.visc_d_param_A_3 * t ** 2)
            B = (b.params.visc_d_param_B_1
                 + b.params.visc_d_param_B_2 * t
                 + b.params.visc_d_param_B_3 * t ** 2)
            return b.visc_d_phase['Liq'] == mu_w * (1 + A * s + B * s ** 2)
        self.eq_visc_d_phase = Constraint(rule=rule_visc_d_phase)

    def _osm_coeff(self):
        self.osm_coeff = Var(
            initialize=1,
            bounds=(1e-8, 10),
            units=pyunits.dimensionless,
            doc="Osmotic coefficient")

        def rule_osm_coeff(b):  # osmotic coefficient, eq. 49 in Sharqawy
            s = b.mass_frac_phase_comp['Liq', 'TDS']
            t = b.temperature - 273.15 * pyunits.K  # temperature in degC, but pyunits are still K
            osm_coeff = (b.params.osm_coeff_param_1
                         + b.params.osm_coeff_param_2 * t
                         + b.params.osm_coeff_param_3 * t ** 2
                         + b.params.osm_coeff_param_4 * t ** 4
                         + b.params.osm_coeff_param_5 * s
                         + b.params.osm_coeff_param_6 * s * t
                         + b.params.osm_coeff_param_7 * s * t ** 3
                         + b.params.osm_coeff_param_8 * s ** 2
                         + b.params.osm_coeff_param_9 * s ** 2 * t
                         + b.params.osm_coeff_param_10 * s ** 2 * t ** 2)
            return b.osm_coeff == osm_coeff
        self.eq_osm_coeff = Constraint(rule=rule_osm_coeff)

    def _pressure_osm(self):
        self.pressure_osm = Var(
            initialize=1e6,
            bounds=(1, 1e8),
            units=pyunits.Pa,
            doc="Osmotic pressure")

        def rule_pressure_osm(b):  # osmotic pressure, based on molality and assumes TDS is NaCl
            i = 2  # number of ionic species
            rhow = 1000 * pyunits.kg/pyunits.m**3  # TODO: could make this variable based on temperature
            return (b.pressure_osm ==
                    i * b.osm_coeff * b.molality_comp['TDS'] * rhow * Constants.gas_constant * b.temperature)
        self.eq_pressure_osm = Constraint(rule=rule_pressure_osm)

    def _enth_mass_phase(self):
        self.enth_mass_phase = Var(
            self.params.phase_list,
            initialize=1e6,
            bounds=(1, 1e9),
            units=pyunits.J * pyunits.kg**-1,
            doc="Specific enthalpy")

        def rule_enth_mass_phase(b):  # specific enthalpy, eq. 55 and 43 in Sharqawy
            t = b.temperature - 273.15 * pyunits.K  # temperature in degC, but pyunits in K
            S = b.mass_frac_phase_comp['Liq', 'TDS']
            h_w = (b.params.enth_mass_param_A1
                   + b.params.enth_mass_param_A2 * t
                   + b.params.enth_mass_param_A3 * t ** 2
                   + b.params.enth_mass_param_A4 * t ** 3)
            # relationship requires dimensionless calculation and units added at end
            h_sw = (h_w -
                    (S * (b.params.enth_mass_param_B1 + S)
                     + S * (b.params.enth_mass_param_B2 + S) * t/pyunits.K)
                    * pyunits.J/pyunits.kg)
            return b.enth_mass_phase['Liq'] == h_sw
        self.eq_enth_mass_phase = Constraint(rule=rule_enth_mass_phase)

    def _enth_flow(self):
        # enthalpy flow expression for get_enthalpy_flow_terms method

        def rule_enth_flow(b):  # enthalpy flow [J/s]
            return sum(b.flow_mass_phase_comp['Liq', j] for j in b.params.component_list) * b.enth_mass_phase['Liq']
        self.enth_flow = Expression(rule=rule_enth_flow)

    # TODO: add vapor pressure, specific heat, thermal conductivity,
    #   and heat of vaporization

    # -----------------------------------------------------------------------------
    # General Methods
    # NOTE: For scaling in the control volume to work properly, these methods must
    # return a pyomo Var or Expression

    def get_material_flow_terms(self, p, j):
        """Create material flow terms for control volume."""
        return self.flow_mass_phase_comp[p, j]

    def get_enthalpy_flow_terms(self, p):
        """Create enthalpy flow terms."""
        return self.enth_flow

    # TODO: make property package compatible with dynamics
    # def get_material_density_terms(self, p, j):
    #     """Create material density terms."""

    # def get_enthalpy_density_terms(self, p):
    #     """Create enthalpy density terms."""

    def default_material_balance_type(self):
        return MaterialBalanceType.componentTotal

    def default_energy_balance_type(self):
        return EnergyBalanceType.enthalpyTotal

    def get_material_flow_basis(b):
        return MaterialFlowBasis.mass

    def define_state_vars(self):
        """Define state vars."""
        return {"flow_mass_phase_comp": self.flow_mass_phase_comp,
                "temperature": self.temperature,
                "pressure": self.pressure}

    # -----------------------------------------------------------------------------
    # Scaling methods
    def calculate_scaling_factors(self):
        super().calculate_scaling_factors()

        # setting scaling factors for variables

        # default scaling factors have already been set with
        # idaes.core.property_base.calculate_scaling_factors()
        # for the following variables: flow_mass_phase_comp, pressure,
        # temperature, dens_mass_phase, visc_d_phase, osm_coeff, and enth_mass_phase

        # these variables should have user input
        if iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'H2O']) is None:
            sf = iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'H2O'], default=1e0, warning=True)
            iscale.set_scaling_factor(self.flow_mass_phase_comp['Liq', 'H2O'], sf)

        if iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'TDS']) is None:
            sf = iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'TDS'], default=1e2, warning=True)
            iscale.set_scaling_factor(self.flow_mass_phase_comp['Liq','TDS'], sf)

        # scaling factors for parameters
        iscale.set_scaling_factor(self.params.mw_comp, 1e-1)

        # these variables do not typically require user input,
        # will not override if the user does provide the scaling factor
        if self.is_property_constructed('pressure_osm'):
            if iscale.get_scaling_factor(self.pressure_osm) is None:
                iscale.set_scaling_factor(self.pressure_osm,
                                          iscale.get_scaling_factor(self.pressure))

        if self.is_property_constructed('mass_frac_phase_comp'):
            for j in self.params.component_list:
                if iscale.get_scaling_factor(self.mass_frac_phase_comp['Liq', j]) is None:
                    if j == 'TDS':
                        sf = (iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', j])
                              / iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'H2O']))
                        iscale.set_scaling_factor(self.mass_frac_phase_comp['Liq', j], sf)
                    elif j == 'H2O':
                        iscale.set_scaling_factor(self.mass_frac_phase_comp['Liq', j], 1)

        if self.is_property_constructed('flow_vol_phase'):
            sf = (iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'H2O'])
                  / iscale.get_scaling_factor(self.dens_mass_phase['Liq']))
            iscale.set_scaling_factor(self.flow_vol_phase, sf)

        if self.is_property_constructed('flow_vol'):
            sf = iscale.get_scaling_factor(self.flow_vol_phase)
            iscale.set_scaling_factor(self.flow_vol, sf)

        if self.is_property_constructed('conc_mass_phase_comp'):
            for j in self.params.component_list:
                sf_dens = iscale.get_scaling_factor(self.dens_mass_phase['Liq'])
                if iscale.get_scaling_factor(self.conc_mass_phase_comp['Liq', j]) is None:
                    if j == 'H2O':
                        # solvents typically have a mass fraction between 0.5-1
                        iscale.set_scaling_factor(self.conc_mass_phase_comp['Liq', j], sf_dens)
                    elif j == 'TDS':
                        iscale.set_scaling_factor(
                            self.conc_mass_phase_comp['Liq', j],
                            sf_dens * iscale.get_scaling_factor(self.mass_frac_phase_comp['Liq', j]))

        if self.is_property_constructed('flow_mol_phase_comp'):
            for j in self.params.component_list:
                if iscale.get_scaling_factor(self.flow_mol_phase_comp['Liq', j]) is None:
                    sf = iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', j])
                    sf *= iscale.get_scaling_factor(self.params.mw_comp[j])
                    iscale.set_scaling_factor(self.flow_mol_phase_comp['Liq', j], sf)

        if self.is_property_constructed('mole_frac_phase_comp'):
            for j in self.params.component_list:
                if iscale.get_scaling_factor(self.mole_frac_phase_comp['Liq', j]) is None:
                    if j == 'TDS':
                        sf = (iscale.get_scaling_factor(self.flow_mol_phase_comp['Liq', j])
                              / iscale.get_scaling_factor(self.flow_mol_phase_comp['Liq', 'H2O']))
                        iscale.set_scaling_factor(self.mole_frac_phase_comp['Liq', j], sf)
                    elif j == 'H2O':
                        iscale.set_scaling_factor(self.mole_frac_phase_comp['Liq', j], 1)

        if self.is_property_constructed('molality_comp'):
            for j in self.params.component_list:
                if isinstance(getattr(self.params, j), Solute):
                    if iscale.get_scaling_factor(self.molality_comp[j]) is None:
                        sf = iscale.get_scaling_factor(self.mass_frac_phase_comp['Liq', j])
                        sf *= iscale.get_scaling_factor(self.params.mw_comp[j])
                        iscale.set_scaling_factor(self.molality_comp[j], sf)

            for j in self.params.component_list:
                sf_dens = iscale.get_scaling_factor(self.dens_mass_phase['Liq'])
                if iscale.get_scaling_factor(self.conc_mass_phase_comp['Liq', j]) is None:
                    if j == 'H2O':
                        # solvents typically have a mass fraction between 0.5-1
                        iscale.set_scaling_factor(self.conc_mass_phase_comp['Liq', j], sf_dens)
                    elif j == 'TDS':
                        iscale.set_scaling_factor(
                            self.conc_mass_phase_comp['Liq', j],
                            sf_dens * iscale.get_scaling_factor(self.mass_frac_phase_comp['Liq', j]))

        if self.is_property_constructed('enth_flow'):
            iscale.set_scaling_factor(self.enth_flow,
                                      iscale.get_scaling_factor(self.flow_mass_phase_comp['Liq', 'H2O'])
                                      * iscale.get_scaling_factor(self.enth_mass_phase['Liq']))

        # transforming constraints
        # property relationships with no index, simple constraint
        v_str_lst_simple = ['osm_coeff', 'pressure_osm']
        for v_str in v_str_lst_simple:
            if self.is_property_constructed(v_str):
                v = getattr(self, v_str)
                sf = iscale.get_scaling_factor(v, default=1, warning=True)
                c = getattr(self, 'eq_' + v_str)
                iscale.constraint_scaling_transform(c, sf)

        # property relationships with phase index, but simple constraint
        v_str_lst_phase = ['dens_mass_phase', 'flow_vol_phase', 'visc_d_phase', 'enth_mass_phase']
        for v_str in v_str_lst_phase:
            if self.is_property_constructed(v_str):
                v = getattr(self, v_str)
                sf = iscale.get_scaling_factor(v['Liq'], default=1, warning=True)
                c = getattr(self, 'eq_' + v_str)
                iscale.constraint_scaling_transform(c, sf)

        # property relationship indexed by component
        v_str_lst_comp = ['molality_comp']
        for v_str in v_str_lst_comp:
            if self.is_property_constructed(v_str):
                v_comp = getattr(self, v_str)
                c_comp = getattr(self, 'eq_' + v_str)
                for j, c in c_comp.items():
                    sf = iscale.get_scaling_factor(v_comp[j], default=1, warning=True)
                    iscale.constraint_scaling_transform(c, sf)

        # property relationships indexed by component and phase
        v_str_lst_phase_comp = ['mass_frac_phase_comp', 'conc_mass_phase_comp', 'flow_mol_phase_comp',
                                'mole_frac_phase_comp']
        for v_str in v_str_lst_phase_comp:
            if self.is_property_constructed(v_str):
                v_comp = getattr(self, v_str)
                c_comp = getattr(self, 'eq_' + v_str)
                for j, c in c_comp.items():
                    sf = iscale.get_scaling_factor(v_comp['Liq', j], default=1, warning=True)
                    iscale.constraint_scaling_transform(c, sf)
