from cacahuate.utils import clear_username


def test_clear_email():
    assert clear_username('kevin@mailinator.com') == 'kevin'
    assert clear_username('a.wonderful.code@gmail.com') == 'awonderfulcode'
    assert clear_username('foo@var.com.mx') == 'foo'
    assert clear_username('foo.var@var.com.mx') == 'foovar'
    assert clear_username('$foo') == 'foo'
