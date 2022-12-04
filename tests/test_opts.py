import winevt_tailer.opts as opts


def test_parse_tailer_config():
    cfg_dic = {'channels': [{'name': 'Test'}]}
    tailer_cfg = opts.parse_tailer_config(cfg_dic)
    fields = dir(tailer_cfg)
    assert all(item in fields for item in ['channels',
                                           'bookmarks_dir',
                                           'bookmarks_commit_s',
                                           'lookback',
                                           'persistent',
                                           'transforms',
                                           'startup_hello',
                                           'exit_after_lookback'])
    assert tailer_cfg.channels[0].name == 'Test'
