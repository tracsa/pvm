from cacahuate.utils import clear_email


def test_clear_email():
    assert clear_email('kevin@mailinator.com') == 'kevin'
    assert clear_email('a.wonderful.code@gmail.com') == 'awonderfulcode'
    assert clear_email('foo@var.com.mx') == 'foo'
    assert clear_email('foo.var@var.com.mx') == 'foovar'
