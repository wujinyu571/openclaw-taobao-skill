from skill.core.parser import parse_positive_rate


def test_parse_positive_rate_with_chinese_label() -> None:
    assert parse_positive_rate("好评率 99.5%") == 99.5


def test_parse_positive_rate_with_suffix() -> None:
    assert parse_positive_rate("99%好评") == 99.0


def test_parse_positive_rate_invalid_text() -> None:
    assert parse_positive_rate("没有好评率字段") is None


def test_parse_positive_rate_boundaries() -> None:
    assert parse_positive_rate("好评率:98.9%") == 98.9
    assert parse_positive_rate("好评率:99%") == 99.0
    assert parse_positive_rate("好评率:100%") == 100.0
