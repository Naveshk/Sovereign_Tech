from app.services.engineering_engine import EngineeringInputError, barlow_pipe_pressure, remaining_life


def test_barlow():
    result = barlow_pipe_pressure(10, 500, 10, 120)
    assert round(result["results"]["hoop_stress_mpa"], 3) == 250.0
    assert round(result["results"]["pressure_capacity_mpa"], 3) == 4.8
    assert result["warnings"]


def test_remaining_life():
    result = remaining_life(12, 8, 0.5)
    assert result["results"]["remaining_thickness_mm"] == 4.0
    assert result["results"]["remaining_life_years"] == 8.0


def test_invalid_remaining_life():
    try:
        remaining_life(7, 8, 0.5)
    except EngineeringInputError:
        return
    raise AssertionError("Expected validation error")


def test_invalid_zero_input():
    try:
        barlow_pipe_pressure(10, 500, 0, 120)
    except EngineeringInputError:
        return
    raise AssertionError("Expected validation error")
