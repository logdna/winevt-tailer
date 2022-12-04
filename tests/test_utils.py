import winevt_tailer.utils as utils


def test_is_valid_xpath():
    good = {'*',
            '*[UserData/*/PrinterName="MyPrinter" and System/Level=1]',
            '*[System[(Level <= 3) and TimeCreated[timediff(@SystemTime) <= 86400000]]]'}
    bad = {'', '\\abc', '!abs', '[abs', '([abs])'}
    for q in good:
        assert utils.is_valid_xpath(q)
    for q in bad:
        assert not utils.is_valid_xpath(q)
