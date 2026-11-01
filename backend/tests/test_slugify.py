from types import SimpleNamespace

import pytest

from app.core.slug import slugify


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", "agency"),
        ("   ", "agency"),
        ("Sunrise Care", "sunrise-care"),
        ("SUNRISE", "sunrise"),
        ("LiveWell 360", "livewell-360"),
        ("A & B Home Care", "a-b-home-care"),
        ("---hello---", "hello"),
        ("hello___world", "hello-world"),
        ("Café Care", "caf-care"),
        ("123 Agency", "123-agency"),
        ("Hyderabad / Secunderabad", "hyderabad-secunderabad"),
        ("a" * 100, "a" * 80),
        ("SafeHome_Ops", "safehome-ops"),
        ("  Multi   Space  ", "multi-space"),
        ("foo.bar", "foo-bar"),
        ("foo@bar.com", "foo-bar-com"),
        ("हिन्दी", "agency"),
        ("LiveWell360™", "livewell360"),
        ("n/a", "n-a"),
        ("OK", "ok"),
    ],
)
def test_slugify_values(value, expected):
    assert slugify(value) == expected


def test_slugify_truncates_to_80():
    slug = slugify("word-" * 30)
    assert len(slug) <= 80
    assert slug.startswith("word")


class _Db:
    def __init__(self, collisions: int):
        self.collisions = collisions
        self.calls = 0
        self.committed = False

    def query(self, model):
        db = self

        class _Query:
            def filter(self, *args, **kwargs):
                return self

            def first(self):
                db.calls += 1
                if db.calls <= db.collisions:
                    return object()
                return None

        return _Query()


def test_ensure_tenant_register_slug_keeps_existing():
    from app.core.slug import ensure_tenant_register_slug

    tenant = SimpleNamespace(register_slug="keep-me", name="Ignored", id=1)
    assert ensure_tenant_register_slug(_Db(0), tenant) == "keep-me"


def test_ensure_tenant_register_slug_assigns_from_name():
    from app.core.slug import ensure_tenant_register_slug

    tenant = SimpleNamespace(register_slug=None, name="Sunrise Care", id=2)
    db = _Db(0)
    assert ensure_tenant_register_slug(db, tenant) == "sunrise-care"
    assert tenant.register_slug == "sunrise-care"


def test_ensure_tenant_register_slug_suffixes_on_collision():
    from app.core.slug import ensure_tenant_register_slug

    tenant = SimpleNamespace(register_slug=None, name="Sunrise Care", id=3)
    assert ensure_tenant_register_slug(_Db(2), tenant) == "sunrise-care-2"
