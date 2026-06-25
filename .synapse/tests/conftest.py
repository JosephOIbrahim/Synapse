import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.dirname(HERE)                       # .synapse/
sys.path.insert(0, SYN)                           # memory.py, verify.py
sys.path.insert(0, os.path.join(SYN, "hooks"))    # fence.py
