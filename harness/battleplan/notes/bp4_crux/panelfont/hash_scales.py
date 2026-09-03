import hashlib, sys
from synapse.panel.designsystem.qss import stylesheet
import synapse.panel.designsystem.qss as q
print("BOUND qss.__file__ =", q.__file__)
for scale in (1.0, 1.15, 1.25, 1.4, 1.6):
    s = stylesheet(scale)
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]
    print(f"scale={scale:<5} sha256[:8]={h}  len={len(s)}")
