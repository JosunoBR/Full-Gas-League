# clean test_syntax.py
import os
try:
    if os.path.exists("test_syntax.py"):
        os.remove("test_syntax.py")
except Exception:
    pass
