"""Sample the machine while a SYNAPSE request runs.

Every SYNAPSE instrument came back clean and it still freezes on an EMPTY scene.
That rules out scene traversal, cooks, grounding payload and the marshal - there
is nothing to traverse.

What is left is something outside SYNAPSE's view, and there is an obvious
candidate that has been in the header the whole time: GLM 5.2. If the model runs
LOCALLY, inference competes with Houdini for the same CPU and GPU, and no
in-process instrument would ever see it. Houdini would stop repainting while
Ollama saturates the box - which is exactly the reported symptom, including
typing still landing (keystrokes buffer) and window resize still working
(handled by Windows, not Qt).

Samples every 500ms for 60s: Houdini CPU, Ollama CPU, GPU utilisation. Fire a
request while it runs.
"""
import subprocess
import time

SAMPLES, INTERVAL = 120, 0.5


def ps(name_like):
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process | Where-Object {$_.ProcessName -match '%s'} | "
         "Measure-Object -Property CPU -Sum | Select-Object -ExpandProperty Sum" % name_like],
        capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def gpu():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True).stdout.strip().splitlines()
        return int(out[0])
    except Exception:
        return -1


print("SAMPLING 60s - FIRE A REQUEST NOW")
print("%-8s %10s %10s %6s" % ("t", "houdini dCPU", "ollama dCPU", "GPU%"))
print("-" * 40)

h_prev, o_prev = ps("houdini"), ps("ollama")
peak = {"h": 0.0, "o": 0.0, "g": 0}
t0 = time.time()

for i in range(SAMPLES):
    time.sleep(INTERVAL)
    h, o, g = ps("houdini"), ps("ollama"), gpu()
    dh, do = h - h_prev, o - o_prev
    h_prev, o_prev = h, o
    peak["h"] = max(peak["h"], dh)
    peak["o"] = max(peak["o"], do)
    peak["g"] = max(peak["g"], g)
    # Only print when something is actually happening.
    if dh > 0.05 or do > 0.05 or g > 20:
        print("%6.1fs %10.2f %10.2f %6d" % (time.time() - t0, dh, do, g))

print("-" * 40)
print("PEAK  houdini %.2f CPU-s/sample | ollama %.2f | GPU %d%%"
      % (peak["h"] / INTERVAL, peak["o"] / INTERVAL, peak["g"]))
print()
print("  ollama peak HIGH + GPU HIGH -> local inference is saturating the box.")
print("     That is the freeze, and it is not a SYNAPSE defect at all.")
print("  ollama near zero -> the model is remote and the freeze is elsewhere.")
