from __future__ import annotations

import io

import numpy as np
import pytest

from core.geometry import (
    GeomModel,
    Grid,
    Rbe3,
    expand_rbe3_displacements,
    parse_f06,
    parse_wireframe_bdf,
)

# ---------------------------------------------------------------------------
# Minimal BDF fixtures (free-field and fixed-field)
# ---------------------------------------------------------------------------

_BDF_FREE = """\
GRID,1,,0.0,0.0,0.0
GRID,2,,1.0,0.0,0.0
GRID,3,,2.0,0.0,0.0
PLOTEL,1,1,2
PLOTEL,2,2,3
"""

# 8-char fixed-field format: keyword(0-7) field2(8-15) field3(16-23) ...
_BDF_FIXED = (
    "GRID    " + "       1" + "        " + "     0.0" + "     0.0" + "     0.0" + "\n"
    "GRID    " + "       2" + "        " + "     1.0" + "     0.0" + "     0.0" + "\n"
    "GRID    " + "       3" + "        " + "     2.0" + "     0.0" + "     0.0" + "\n"
    "PLOTEL  " + "       1" + "       1" + "       2" + "\n"
    "PLOTEL  " + "       2" + "       2" + "       3" + "\n"
)

_F06_MINIMAL = """\
                                          R E A L   E I G E N V A L U E S

   MODE NO.      EIGENVALUE            RADIANS             CYCLES             GENERALIZED MASS
         1   2.624605E+02   1.620063E+01   1.000000E+01   1.000000E+00
         2   1.030853E+04   1.015309E+02   2.000000E+01   1.000000E+00

                          E I G E N V E C T O R   NO. 1     FREQ = 1.000000E+01 Hz

      POINT ID.   TYPE          T1             T2             T3             R1             R2             R3
             1     G   1.000000E+00 0.000000E+00 0.000000E+00 0.000000E+00 0.000000E+00 0.000000E+00

                          E I G E N V E C T O R   NO. 2     FREQ = 2.000000E+01 Hz

      POINT ID.   TYPE          T1             T2             T3             R1             R2             R3
             1     G   0.000000E+00 1.000000E+00 0.000000E+00 0.000000E+00 0.000000E+00 0.000000E+00
"""


# ---------------------------------------------------------------------------
# parse_wireframe_bdf
# ---------------------------------------------------------------------------


def test_parse_wireframe_bdf_grid_count_free_field():
    geom = parse_wireframe_bdf(io.StringIO(_BDF_FREE))
    assert len(geom.grids) == 3
    assert len(geom.plotels) == 2


def test_parse_wireframe_bdf_grid_count_fixed_field():
    geom = parse_wireframe_bdf(io.StringIO(_BDF_FIXED))
    assert len(geom.grids) == 3
    assert len(geom.plotels) == 2


def test_parse_wireframe_bdf_free_and_fixed_agree():
    geom_free = parse_wireframe_bdf(io.StringIO(_BDF_FREE))
    geom_fixed = parse_wireframe_bdf(io.StringIO(_BDF_FIXED))
    assert set(geom_free.grids.keys()) == set(geom_fixed.grids.keys())
    assert set(geom_free.plotels.keys()) == set(geom_fixed.plotels.keys())
    for gid in geom_free.grids:
        gf, gx = geom_free.grids[gid], geom_fixed.grids[gid]
        assert pytest.approx(gf.x) == gx.x
        assert pytest.approx(gf.y) == gx.y
        assert pytest.approx(gf.z) == gx.z


def test_parse_wireframe_bdf_grid_coordinates():
    geom = parse_wireframe_bdf(io.StringIO(_BDF_FREE))
    assert pytest.approx(geom.grids[1].x) == 0.0
    assert pytest.approx(geom.grids[2].x) == 1.0
    assert pytest.approx(geom.grids[3].x) == 2.0


def test_parse_wireframe_bdf_empty_model():
    geom = parse_wireframe_bdf(io.StringIO(""))
    assert len(geom.grids) == 0
    assert len(geom.plotels) == 0


# ---------------------------------------------------------------------------
# parse_f06
# ---------------------------------------------------------------------------


def test_parse_f06_frequency_count():
    result = parse_f06(io.StringIO(_F06_MINIMAL))
    assert len(result["frequencies_hz"]) == 2


def test_parse_f06_frequency_values():
    result = parse_f06(io.StringIO(_F06_MINIMAL))
    freqs = result["frequencies_hz"]
    assert pytest.approx(freqs[0], rel=1e-4) == 10.0
    assert pytest.approx(freqs[1], rel=1e-4) == 20.0


def test_parse_f06_mode_shape_count():
    result = parse_f06(io.StringIO(_F06_MINIMAL))
    assert len(result["mode_shapes"]) == 2


def test_parse_f06_mode_shape_values():
    result = parse_f06(io.StringIO(_F06_MINIMAL))
    mode1 = result["mode_shapes"][0]
    assert 1 in mode1
    np.testing.assert_allclose(mode1[1], [1.0, 0.0, 0.0], atol=1e-6)

    mode2 = result["mode_shapes"][1]
    assert 1 in mode2
    np.testing.assert_allclose(mode2[1], [0.0, 1.0, 0.0], atol=1e-6)


# ---------------------------------------------------------------------------
# expand_rbe3_displacements
# ---------------------------------------------------------------------------


def test_expand_rbe3_displacements_weighted_average():
    grids = {
        1: Grid(gid=1, x=0.0, y=0.0, z=0.0),
        2: Grid(gid=2, x=1.0, y=0.0, z=0.0),
        3: Grid(gid=3, x=0.5, y=0.0, z=0.0),  # refgrid
    }
    rbe3 = Rbe3(eid=1, refgrid=3, refc="123", wt_gc=[(1.0, "3", [1, 2])])
    geom = GeomModel(grids=grids, plotels={}, rbe3s={1: rbe3})

    meas_disps = {
        1: np.array([1.0, 0.0, 0.0]),
        2: np.array([3.0, 0.0, 0.0]),
    }
    result = expand_rbe3_displacements(geom, meas_disps)
    # Equal weights on grids 1 and 2: refgrid = (1+3)/2 = 2.0
    np.testing.assert_allclose(result[3][0], 2.0, atol=1e-10)


def test_expand_rbe3_displacements_direct_passthrough():
    grids = {1: Grid(gid=1, x=0.0, y=0.0, z=0.0)}
    geom = GeomModel(grids=grids, plotels={}, rbe3s={})
    meas_disps = {1: np.array([5.0, 3.0, 1.0])}
    result = expand_rbe3_displacements(geom, meas_disps)
    np.testing.assert_allclose(result[1], [5.0, 3.0, 1.0])


def test_expand_rbe3_displacements_zero_for_unmeasured():
    grids = {
        1: Grid(gid=1, x=0.0, y=0.0, z=0.0),
        2: Grid(gid=2, x=1.0, y=0.0, z=0.0),
    }
    geom = GeomModel(grids=grids, plotels={}, rbe3s={})
    result = expand_rbe3_displacements(geom, {1: np.array([1.0, 0.0, 0.0])})
    np.testing.assert_allclose(result[2], [0.0, 0.0, 0.0])
