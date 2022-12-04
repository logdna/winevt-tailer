from winevt_tailer.tailer import Tailer
import winevt_tailer.opts as opts


def test_stop():
    cfg_dic = {'channels': [{'name': 'Test'}]}
    tailer_cfg = opts.parse_tailer_config(cfg_dic)
    tailer = Tailer('test_tailer', tailer_cfg)
    assert tailer.is_stop is False
    res1 = tailer.stop()
    assert res1 is True
    assert tailer.is_stop is True
    res2 = tailer.stop()
    assert res2 is False
