import pytest

from ...conftest import DocumentCapturer


@pytest.fixture
def test_docs():
    return [
        ("start", {"uid": 12345, "abc": 56789, "xyz": 99999}),
        ("stop", {"uid": 77777, "abc": 88888, "xyz": 99999}),
    ]


def test_callback_sim_doc_names(test_docs):
    DocumentCapturer.assert_doc(test_docs, "start")
    DocumentCapturer.assert_doc(test_docs, "stop")
    DocumentCapturer.assert_doc(test_docs, "restart", does_exist=False)


def test_callback_sim_has_fields(test_docs):
    DocumentCapturer.assert_doc(test_docs, "start", has_fields=["uid"])
    DocumentCapturer.assert_doc(test_docs, "stop", has_fields=["abc", "xyz"])
    DocumentCapturer.assert_doc(
        test_docs, "start", has_fields=["uid", "bbb"], does_exist=False
    )


def test_callback_sim_matches_fields(test_docs):
    DocumentCapturer.assert_doc(test_docs, "start", matches_fields={"uid": 12345})
    DocumentCapturer.assert_doc(
        test_docs, "stop", matches_fields={"abc": 88888, "xyz": 99999}
    )
    DocumentCapturer.assert_doc(
        test_docs,
        "start",
        matches_fields={"abc": 88888, "xyz": 99799},
        does_exist=False,
    )


def test_callback_sim_assert_switch(test_docs):
    with pytest.raises(AssertionError):
        DocumentCapturer.assert_doc(test_docs, "restart")

    with pytest.raises(AssertionError):
        DocumentCapturer.assert_doc(test_docs, "start", has_fields=["uid", "bbb"])

    with pytest.raises(AssertionError):
        DocumentCapturer.assert_doc(
            test_docs, "start", matches_fields={"abc": 88888, "xyz": 99799}
        )
