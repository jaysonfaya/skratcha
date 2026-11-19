"""SKRATCHA: merge the German and the English skin into one skin with a language switch.

    merge_lang.py <skin_de> <skin_en> <out> <params.json>

Both skins come from the same build (ui25.py), once with SKR_LANG=en. Every image that differs gets an English copy
(<name>_en.png); every component definition that uses such an image gets an English twin (<key>_EN); every placed
component that shows German text is placed twice: the German one visible while Language = DEUTSCH, the English one
while Language = ENGLISH (the same IndexedEnabling mechanism the skin uses for decks, eras and lessons).
"""
import filecmp
import json
import os
import shutil
import sys

de_dir, en_dir, out_dir, params_path = sys.argv[1:5]
params = json.load(open(params_path))
plist = params["params"] if isinstance(params, dict) else params
P = {p["name"]: i for i, p in enumerate(plist)}
LANG = P["Language"]


def lang_is(v):
    return "IndexedEnabling/%d/2/Parameter %d" % (v, LANG)


if os.path.exists(out_dir):
    shutil.rmtree(out_dir)
shutil.copytree(de_dir, out_dir)

# 1. images that differ
diff = set()
for root, _, files in os.walk(en_dir):
    for fn in files:
        if not fn.endswith(".png"):
            continue
        rel = os.path.relpath(os.path.join(root, fn), en_dir)
        a, b = os.path.join(de_dir, rel), os.path.join(en_dir, rel)
        if not os.path.exists(a) or not filecmp.cmp(a, b, shallow=False):
            diff.add(rel)
            dst = os.path.join(out_dir, rel[:-4] + "_en.png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(b, dst)
print("images with text that differs:", len(diff))


def en_name(img):
    return img[:-4] + "_en.png" if img in diff else img


def uses_diff(o):
    if isinstance(o, dict):
        return any(uses_diff(v) for v in o.values())
    if isinstance(o, list):
        return any(uses_diff(v) for v in o)
    return isinstance(o, str) and o in diff


def to_en(o):
    if isinstance(o, dict):
        return {k: to_en(v) for k, v in o.items()}
    if isinstance(o, list):
        return [to_en(v) for v in o]
    if isinstance(o, str) and o in diff:
        return en_name(o)
    return o


tui_de = json.load(open(os.path.join(de_dir, "TUI.json")))
L = tui_de["pageData"]["componentDefinitions"]["localComponentDefinitions"]
defs = {d["key"]: d for d in L}
tabs = {t["componentName"] for t in tui_de["pageData"]["tabs"]}

# 2. definitions that use such images get an English twin
twin = {}
for d in list(L):
    if d["key"] in tabs:
        continue
    if uses_diff(d["value"]):
        e = {"key": d["key"] + "_EN", "value": to_en(d["value"])}
        L.append(e)
        twin[d["key"]] = e["key"]
print("definitions with an English twin:", len(twin))


def add_cond(comp, v):
    b = comp["bounds"]
    b["additionalInvalidatingHandles"] = list(b.get("additionalInvalidatingHandles", [])) + [lang_is(v)]
    b["showWhenDataModelInvalid"] = "Hide"


# 3. placed components: German + English copy
placed = 0
for d in L:
    if d["key"] not in tabs:
        continue
    comps = d["value"]["componentsData"]
    out = []
    for c in comps:
        cd = c["componentData"]
        typ = cd["type"]
        en = None
        if typ in twin:
            en = json.loads(json.dumps(c)); en["componentData"]["type"] = twin[typ]; en["componentData"]["name"] += "_en"
        elif typ == "Image" and uses_diff(cd.get("data", {})):
            en = json.loads(json.dumps(c)); en["componentData"]["data"] = to_en(cd["data"]); en["componentData"]["name"] += "_en"
        if en is None:
            out.append(c)
            continue
        if cd.get("name") == "Background":
            # the English background is drawn right above the German one (both full size; controls stay on top)
            add_cond(en, 1)
            out.append(c); out.append(en)
        else:
            add_cond(c, 0); add_cond(en, 1)
            out.append(c); out.append(en)
        placed += 1
    d["value"]["componentsData"] = out
print("placed twice:", placed)

# tab names are fixed text: the one German name gets both
for t in tui_de["pageData"]["tabs"]:
    if t["tabName"] == "LERNEN":
        t["tabName"] = "LERNEN / LEARN"

json.dump(tui_de, open(os.path.join(out_dir, "TUI.json"), "w"), indent=1)
print("merged skin written:", out_dir)
