from types import SimpleNamespace

from app.services.us_compliance_helpers import (
    CLASSIFICATION_1099,
    CLASSIFICATION_W2,
    get_classification,
    is_1099_contractor,
)


class _Query:
    def __init__(self, row):
        self.row = row

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row

    def query(self, model):
        return _Query(self.row)


def test_default_classification_is_w2():
    assert get_classification(_Db(None), 1, 1) == CLASSIFICATION_W2
    assert is_1099_contractor(_Db(None), 1, 1) is False


def test_stored_1099_is_uppercased():
    row = SimpleNamespace(classification="1099_contractor")
    assert get_classification(_Db(row), 1, 1) == CLASSIFICATION_1099
    assert is_1099_contractor(_Db(row), 1, 1) is True


def test_stored_w2():
    row = SimpleNamespace(classification="w2_employee")
    assert get_classification(_Db(row), 2, 2) == CLASSIFICATION_W2
    assert is_1099_contractor(_Db(row), 2, 2) is False
