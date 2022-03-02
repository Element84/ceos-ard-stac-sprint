from pathlib import Path

from ceos_ard_validator.validate import validate


def data_file(file_name: str) -> str:
    return str(Path(__file__).parent / "data-files" / file_name)


def test_invalid():
    results = validate(data_file("LC09_L2SP_092067_20220228_20220302_02_T1_SR.json"))
    assert results
