###############################################################################
# WaterTAP Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#
###############################################################################
"""
Tests for zero-order chemical addition model
"""
import pytest
from io import StringIO

from pyomo.environ import ConcreteModel, Constraint, Param, value, Var
from pyomo.util.check_units import assert_units_consistent

from idaes.core import FlowsheetBlock
from idaes.core.util import get_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.testing import initialization_tester
from idaes.core.util.exceptions import ConfigurationError

from watertap.unit_models.zero_order import ChemicalAdditionZO
from watertap.core.wt_database import Database
from watertap.core.zero_order_properties import WaterParameterBlock

solver = get_solver()


@pytest.mark.unit
def test_no_subtype():
    m = ConcreteModel()
    m.db = Database()

    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.params = WaterParameterBlock(
        default={"solute_list": ["sulfur", "toc", "tss"]})

    with pytest.raises(ConfigurationError,
                       match="fs.unit - zero-order chemical addition "
                       "operations require the process_subtype configuration "
                       "argument to be set"):
        m.fs.unit = ChemicalAdditionZO(default={
            "property_package": m.fs.params,
            "database": m.db})


class TestChemAddZOAmmonia:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["sulfur", "toc", "tss"]})

        m.fs.unit = ChemicalAdditionZO(default={
            "property_package": m.fs.params,
            "database": m.db,
            "process_subtype": "default"})

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(1000)
        m.fs.unit.inlet.flow_mass_comp[0, "sulfur"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "toc"].fix(2)
        m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(3)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database == model.db

        assert isinstance(model.fs.unit.chemical_dosage, Var)
        assert isinstance(model.fs.unit.chemical_flow_vol, Var)
        assert isinstance(model.fs.unit.solution_density, Var)
        assert isinstance(model.fs.unit.ratio_in_solution, Var)
        assert isinstance(model.fs.unit.chemical_flow_constraint, Constraint)

        assert isinstance(model.fs.unit.lift_height, Param)
        assert isinstance(model.fs.unit.eta_pump, Param)
        assert isinstance(model.fs.unit.eta_motor, Param)
        assert isinstance(model.fs.unit.electricity, Var)
        assert isinstance(model.fs.unit.electricity_consumption, Constraint)

    @pytest.mark.component
    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("chemical_addition")

        model.fs.unit.load_parameters_from_database()

        assert model.fs.unit.chemical_dosage[0].fixed
        assert model.fs.unit.chemical_dosage[0].value == 1

        assert model.fs.unit.solution_density.fixed
        assert model.fs.unit.solution_density.value == 1000

        assert model.fs.unit.ratio_in_solution.fixed
        assert model.fs.unit.ratio_in_solution.value == 0.5

    @pytest.mark.component
    def test_degrees_of_freedom(self, model):
        assert degrees_of_freedom(model.fs.unit) == 0

    @pytest.mark.component
    def test_unit_consistency(self, model):
        assert_units_consistent(model.fs.unit)

    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        for t, j in model.fs.unit.inlet.flow_mass_comp:
            assert (pytest.approx(value(
                model.fs.unit.inlet.flow_mass_comp[t, j]), rel=1e-5) ==
                value(model.fs.unit.outlet.flow_mass_comp[t, j]))

        assert (pytest.approx(2.012e-6, rel=1e-5) ==
                value(model.fs.unit.chemical_flow_vol[0]))

        assert (pytest.approx(7.41395e-4, rel=1e-5) ==
                value(model.fs.unit.electricity[0]))

    @pytest.mark.component
    def test_report(self, model):
        stream = StringIO()

        model.fs.unit.report(ostream=stream)

        output = """
====================================================================================
Unit : fs.unit                                                             Time: 0.0
------------------------------------------------------------------------------------
    Unit Performance

    Variables: 

    Key                : Value      : Fixed : Bounds
       Chemical Dosage :     1.0000 :  True : (0, None)
         Chemical Flow : 2.0120e-06 : False : (0, None)
    Electricity Demand : 0.00074140 : False : (None, None)

------------------------------------------------------------------------------------
    Stream Table
                                Inlet  Outlet
    Volumetric Flowrate        1.0060  1.0060
    Mass Concentration H2O     994.04  994.04
    Mass Concentration sulfur 0.99404 0.99404
    Mass Concentration toc     1.9881  1.9881
    Mass Concentration tss     2.9821  2.9821
====================================================================================
"""

        assert output == stream.getvalue()


db = Database()
params = db._get_technology("chemical_addition")


class TestPumpZOsubtype:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["sulfur", "toc", "tss"]})

        return m

    @pytest.mark.parametrize("subtype", [params.keys()])
    @pytest.mark.component
    def test_load_parameters(self, model, subtype):
        model.fs.unit = ChemicalAdditionZO(default={
            "property_package": model.fs.params,
            "database": db,
            "process_subtype": subtype})

        model.fs.unit.config.process_subtype = subtype
        data = db.get_unit_operation_parameters(
            "chemical_addition", subtype=subtype)

        model.fs.unit.load_parameters_from_database()

        assert model.fs.unit.chemical_dosage[0].fixed
        assert model.fs.unit.chemical_dosage[0].value == data[
            "chemical_dosage"]["value"]

        assert model.fs.unit.solution_density.fixed
        assert model.fs.unit.solution_density.value == data[
            "solution_density"]["value"]

        assert model.fs.unit.ratio_in_solution.fixed
        assert model.fs.unit.ratio_in_solution.value == data[
            "ratio_in_solution"]["value"]
