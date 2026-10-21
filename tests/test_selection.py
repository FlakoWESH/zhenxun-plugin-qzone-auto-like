import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "qzone_auto_like" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_qzone_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


selection = _load("selection")

select_comment_candidates = selection.select_comment_candidates
select_like_candidates = selection.select_like_candidates


def _post(tid: str, uin: str) -> SimpleNamespace:
    return SimpleNamespace(tid=tid, uin=uin)


def test_like_selection_skips_denied_and_existing():
    posts = [_post("a", "1"), _post("b", "2"), _post("c", "3"), _post("d", "4")]
    result = select_like_candidates(
        posts, denied={"2"}, existing={"c"}, limit=2
    )
    assert [post.tid for post in result] == ["a", "d"]


def test_like_selection_allows_unknown_author():
    posts = [_post("a", "")]
    assert [post.tid for post in select_like_candidates(posts)] == ["a"]


def test_comment_selection_requires_allowlist_and_skips_self():
    posts = [
        _post("a", "1"),
        _post("b", "2"),
        _post("c", "987133660"),
        _post("d", "3"),
    ]
    result = select_comment_candidates(
        posts,
        allowed={"1", "987133660", "3"},
        existing={"d"},
        self_qq="987133660",
        limit=5,
    )
    assert [post.tid for post in result] == ["a"]


def test_comment_selection_respects_limit():
    posts = [_post(str(i), "1") for i in range(10)]
    result = select_comment_candidates(
        posts, allowed={"1"}, self_qq="2", limit=3
    )
    assert len(result) == 3
