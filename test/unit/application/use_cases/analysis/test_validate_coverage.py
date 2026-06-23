import pytest

from src.application.use_cases.analysis.validate_coverage import ValidateCoverageDistributionUseCase


async def _run(cobertura_xml: str) -> dict:
    result = await ValidateCoverageDistributionUseCase().execute(cobertura_xml)
    return result.model_dump()


def _make_xml(packages: list[tuple[str, int, int]]) -> str:
    """Build minimal Cobertura XML matching coverage.py's actual output format.

    packages is a list of (name, lines_valid, lines_covered).
    Coverage is represented via <line hits="N"> elements inside each package,
    NOT via lines-valid/lines-covered attributes on <package> (those don't exist
    in coverage.py's Cobertura output — only line-rate is on <package>).
    """
    pkg_parts: list[str] = []
    for name, valid, covered in packages:
        line_elems = "".join(
            f'<line number="{j + 1}" hits="{"1" if j < covered else "0"}"/>'
            for j in range(valid)
        )
        pkg_parts.append(
            f'<package name="{name}" line-rate="0" branch-rate="0" complexity="0">'
            f'<classes><class name="m.py" filename="{name}.py" '
            f'line-rate="0" branch-rate="0" complexity="0">'
            f"<methods/><lines>{line_elems}</lines></class></classes></package>"
        )
    return (
        '<?xml version="1.0" ?><coverage><packages>'
        + "".join(pkg_parts)
        + "</packages></coverage>"
    )


# ── all layers passing ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_layers_above_threshold_is_clean():
    xml = _make_xml([
        ("src.domain.entities", 100, 95),       # 95% ≥ 90%
        ("src.application.use_cases", 100, 90),  # 90% ≥ 85%
        ("src.infrastructure", 100, 70),         # 70% ≥ 65%
        ("src.presentation", 100, 60),           # 60% ≥ 55%
    ])
    r = await _run(xml)
    assert r["status"] == "clean"
    assert r["findings"] == []


# ── layer below threshold (required) ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_domain_below_threshold_is_violation():
    xml = _make_xml([("src.domain.entities", 100, 80)])  # 80% < 90%
    r = await _run(xml)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/coverage/domain-below-threshold" in ids


@pytest.mark.asyncio
async def test_application_below_threshold_is_violation():
    xml = _make_xml([("src.application.use_cases", 100, 80)])  # 80% < 85%
    r = await _run(xml)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/coverage/application-below-threshold" in ids


@pytest.mark.asyncio
async def test_infrastructure_below_threshold_is_violation():
    xml = _make_xml([("src.infrastructure.repositories", 100, 60)])  # 60% < 65%
    r = await _run(xml)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/coverage/infrastructure-below-threshold" in ids


@pytest.mark.asyncio
async def test_presentation_below_threshold_is_violation():
    xml = _make_xml([("src.presentation.routes", 100, 50)])  # 50% < 55%
    r = await _run(xml)
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/coverage/presentation-below-threshold" in ids


# ── aggregation across packages in the same layer ─────────────────────────────

@pytest.mark.asyncio
async def test_layer_coverage_is_aggregated_across_packages():
    # Two domain packages: 80/100 + 100/100 = 180/200 = 90% → passes
    xml = _make_xml([
        ("src.domain.entities", 100, 80),
        ("src.domain.value_objects", 100, 100),
    ])
    r = await _run(xml)
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_aggregated_layer_still_fails_when_too_low():
    # Two domain packages: 50/100 + 60/100 = 110/200 = 55% < 90% → violation
    xml = _make_xml([
        ("src.domain.entities", 100, 50),
        ("src.domain.value_objects", 100, 60),
    ])
    r = await _run(xml)
    assert r["status"] == "violations"
    ids = [f["rule_id"] for f in r["findings"]]
    assert "qa/coverage/domain-below-threshold" in ids


# ── unknown packages are skipped ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_layer_packages_are_ignored():
    xml = _make_xml([
        ("scripts.seed", 100, 0),   # 0% — but not a tracked layer
        ("src.domain.entities", 100, 95),  # passes
    ])
    r = await _run(xml)
    assert r["status"] == "clean"


@pytest.mark.asyncio
async def test_layer_with_zero_valid_lines_is_skipped():
    # A layer entry with lines-valid=0 should not produce a false violation
    xml = _make_xml([("src.domain.entities", 0, 0)])
    r = await _run(xml)
    assert r["status"] == "clean"


# ── edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_xml_raises_value_error():
    with pytest.raises(ValueError, match="cobertura_xml is empty"):
        await ValidateCoverageDistributionUseCase().execute("")


@pytest.mark.asyncio
async def test_invalid_xml_raises_value_error():
    with pytest.raises(ValueError, match="Invalid XML"):
        await ValidateCoverageDistributionUseCase().execute("not xml at all")


@pytest.mark.asyncio
async def test_finding_location_is_layer_prefixed():
    xml = _make_xml([("src.domain.entities", 100, 50)])
    r = await _run(xml)
    f = r["findings"][0]
    assert f["location"] == "layer:domain"
