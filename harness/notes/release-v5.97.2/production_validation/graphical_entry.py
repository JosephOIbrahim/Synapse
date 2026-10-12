"""Houdini command-line .py entry, after supported waitforui; owned process only."""
import json
import os
from pathlib import Path
import runpy
import sys
import traceback

root = Path(os.environ['SYNAPSE_GUI_PACKET'])
arguments = json.loads(os.environ['SYNAPSE_GUI_PROBE_ARGUMENTS'])
sys.argv = [str(root / 'production_probe.py')] + arguments
code = 1
try:
    definitions = runpy.run_path(str(root / 'production_probe.py'), run_name='owned_graphical_probe')
    code = definitions['main']()
except Exception:
    Path(os.environ['SYNAPSE_GUI_RUN_ROOT'], 'graphical-bootstrap-error.txt').write_text(traceback.format_exc(), encoding='utf-8')
finally:
    import hou
    hou.exit(exit_code=code, suppress_save_prompt=True)
