import json, sys
s = json.load(open(sys.argv[1], encoding="utf-8"))["summary"]
for k in ("density", "chrome_scale", "host_font", "n_text_widgets", "px_hist", "family_hist",
          "weight_hist", "spacing_hist", "caps_hist", "italic", "wordmark", "styles_registered"):
    print(k, "=", json.dumps(s[k]))
print("CLIPPED", len(s["clipped"]))
for c in s["clipped"]:
    print("   ", json.dumps(c))
print("PROBES", json.dumps(s["probes"]))
