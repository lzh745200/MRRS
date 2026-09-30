
import importlib, sys
sys.path.insert(0, ".")
import app.schemas as pkg
names_now = set(pkg.__all__)
from pydantic import BaseModel as _BM
mods = ["auth","fund","policy","project","school","user","village"]
old = set()
for m in mods:
    mod = importlib.import_module("app.schemas." + m)
    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if isinstance(attr, type) and issubclass(attr, _BM):
            old.add(attr_name)
removed = sorted(old - names_now)
print("REGISTERED", len(names_now))
print("REMOVED", removed)
