import sys
from io import StringIO
import json
import winevt_tailer.main as tailer_main


def test_cli_no_args():
    old_stdout = sys.stdout
    sys.stdout = tail_out = StringIO()
    try:
        argv = {}
        tailer_main.main(argv)
        out = tail_out.getvalue()
        lines = out.strip().split("\n")
        for line in lines:
            json.loads(line)
            assert (line.find("Binary") < 0)
            # in cli mode only. and in service mode - EventData is not removed
            assert ((line.find("EventData") < 0 and line.find("Message") > 0) or line.find("Message") < 0)
    finally:
        sys.stdout = old_stdout
