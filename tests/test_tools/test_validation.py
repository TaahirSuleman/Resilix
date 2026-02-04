from resilix.tools.validation_tools import code_validation


def test_code_validation_success():
    result = code_validation("x = 1\n")
    assert result["valid"] is True


def test_code_validation_failure():
    result = code_validation("def")
    assert result["valid"] is False
    assert result["error"]
