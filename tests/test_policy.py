import importlib.util
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "qzone_auto_like" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_qzone_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = _load("policy")

DEFAULT_COMMENT_TEMPLATE = policy.DEFAULT_COMMENT_TEMPLATE
choose_template = policy.choose_template
format_qq_list = policy.format_qq_list
normalize_template = policy.normalize_template
parse_interval = policy.parse_interval
parse_target_qq = policy.parse_target_qq
render_template = policy.render_template
should_comment = policy.should_comment
should_like = policy.should_like


def test_normalize_template_accepts_common_inputs():
    assert normalize_template("QεQ") == "QεQ"
    assert normalize_template("  +QεQ  ") == "QεQ"
    assert normalize_template("＋今天也要开心") == "今天也要开心"


def test_normalize_template_rejects_invalid_values():
    assert normalize_template("") is None
    assert normalize_template("   ") is None
    assert normalize_template("a\nb") is None
    assert normalize_template("x" * 101) is None


def test_parse_interval():
    assert parse_interval("120") == 120
    assert parse_interval("设置监控间隔120") == 120
    assert parse_interval("30") == 30
    assert parse_interval("3600") == 3600
    assert parse_interval("29") is None
    assert parse_interval("3601") is None
    assert parse_interval("abc") is None


def test_parse_target_qq_prefers_at_and_rejects_self():
    assert parse_target_qq("", ["947142539"], self_qq="987133660") == "947142539"
    assert parse_target_qq("＋947142539", [], self_qq="987133660") == "947142539"
    assert parse_target_qq("947142539", ["123456"], self_qq="987133660") == "123456"
    assert parse_target_qq("987133660", [], self_qq="987133660") is None
    assert parse_target_qq("", [], self_qq="987133660") is None


def test_should_like_and_comment_defaults():
    assert should_like(True, None) is True
    assert should_like(True, True) is True
    assert should_like(True, False) is False
    assert should_like(False, True) is False

    assert should_comment(True, None) is False
    assert should_comment(True, True) is True
    assert should_comment(True, False) is False
    assert should_comment(False, True) is False


def test_choose_and_render_template():
    assert choose_template(None, "QεQ") == "QεQ"
    assert choose_template("个人", "QεQ") == "个人"
    assert choose_template(None, None) == DEFAULT_COMMENT_TEMPLATE
    assert render_template("你好，{nickname}", "小明") == "你好，小明"
    assert render_template("你好，{nickname}", "") == "你好，你"


def test_format_qq_list():
    assert format_qq_list([]) == "（空）"
    assert format_qq_list(["1", "2"]) == "1、2"
    assert "等 5 人" in format_qq_list(["1", "2", "3", "4", "5"], limit=2)
