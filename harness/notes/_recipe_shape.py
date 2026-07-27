"""What shape is a RecipeRegistry entry, and can the palette render it?

S3-F3: the palette shows 21 recipes from panel/recipe_book.RECIPES while
routing/recipes/RecipeRegistry holds 62. 41 are unreachable from the palette -
function without affordance.

Before wiring anything, find out what a registry recipe actually carries.
"""
import sys
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
sys.path.insert(0, r"C:\Users\User\SYNAPSE")

from synapse.routing.recipes import RecipeRegistry

r = RecipeRegistry()

# find the container whatever it is called
d = None
for attr in ("_recipes", "recipes", "_registry", "registry"):
    v = getattr(r, attr, None)
    if isinstance(v, dict) and v:
        d = v
        print("container attr:", attr, "count:", len(v))
        break

if d is None:
    print("no dict container found. dir():")
    print([a for a in dir(r) if not a.startswith("__")][:25])
    raise SystemExit

key = list(d)[0]
rec = d[key]
print()
print("first key :", key)
print("type      :", type(rec).__name__)
print()
print("fields:")
for f in sorted(a for a in dir(rec) if not a.startswith("_")):
    try:
        v = getattr(rec, f)
    except Exception:
        continue
    if callable(v):
        continue
    print("  .%-16s %s" % (f, str(v)[:80]))

print()
print("categories present:")
cats = {}
for k, v in d.items():
    c = getattr(v, "category", None) or "?"
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print("  %-16s %d" % (c, n))
