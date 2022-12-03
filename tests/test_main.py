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
        lines = tail_out.getvalue().strip().split("\n")
        for line in lines:
            json.loads(line)
    finally:
        sys.stdout = old_stdout
