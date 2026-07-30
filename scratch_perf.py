# cleanup scratch
import os
try:
    if os.path.exists("scratch_perf.py"):
        os.remove("scratch_perf.py")
except Exception:
    pass
