from pathlib import Path
from single_source import get_version
import os
import winevt_tailer.errors as errors

__version__ = get_version(__name__, Path(__file__).parent.parent)

if os.name != 'nt':
    raise errors.TailerError("This code is designed to run only on Windows!")
