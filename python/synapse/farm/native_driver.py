"""Detached supervisor and native Houdini worker; never imported by the artist host.

H22.0.400 authority: native pdgjob.topcook.cookTopNode plus runtime probes in
checks/tops-implementation/runtime-probe. Every render has an owned watchdog.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

if __package__:
    from . import package as pkg
else:
    import package as pkg


class ProcessTree:
    """Own only the just-created worker tree; fail closed if ownership fails."""

    def __init__(self, process):
        self.process = process
        self.handle = None
        self.quiescent = False
        self.process_handles = {}
        self.verified_process_count = 0
        if os.name != "nt":
            return
        import ctypes
        from ctypes import wintypes
        self.ctypes = ctypes
        self.wintypes = wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in (
                "TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
            _fields_ += [(name, wintypes.DWORD) for name in (
                "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]
        self.Accounting = Accounting

        kernel = self.kernel
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                   ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "Could not create owned process group")
        self.handle = handle
        limits = Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if (not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle)))):
            error = ctypes.get_last_error()
            kernel.CloseHandle(handle)
            self.handle = None
            raise OSError(error, "Could not own the detached worker process group")

    def _active_processes(self):
        accounting = self.Accounting()
        if not self.kernel.QueryInformationJobObject(self.handle, 1,
                self.ctypes.byref(accounting), self.ctypes.sizeof(accounting), None):
            raise OSError(self.ctypes.get_last_error(), "Could not query the owned worker group")
        return int(accounting.ActiveProcesses)

    def remember_processes(self):
        """Hold query/synchronization handles for members of this exact job only."""
        if not self.handle:
            return
        ctypes, wintypes = self.ctypes, self.wintypes
        capacity = 32
        while capacity <= 4096:
            class ProcessIds(ctypes.Structure):
                _fields_ = [("assigned", wintypes.DWORD), ("returned", wintypes.DWORD),
                            ("pids", ctypes.c_size_t * capacity)]
            info = ProcessIds()
            success = self.kernel.QueryInformationJobObject(self.handle, 3,
                ctypes.byref(info), ctypes.sizeof(info), None)
            if success and info.assigned <= info.returned:
                break
            if not success and ctypes.get_last_error() != 234:
                raise OSError(ctypes.get_last_error(), "Could not enumerate the owned process group")
            capacity *= 2
        else:
            raise RuntimeError("The owned process list exceeded the supported inspection bound.")
        for pid in info.pids[:info.returned]:
            if pid in self.process_handles:
                if self.kernel.WaitForSingleObject(self.process_handles[pid], 0) == 258:
                    continue
                self.kernel.CloseHandle(self.process_handles.pop(pid))
            handle = self.kernel.OpenProcess(0x1000 | 0x100000, False, pid)
            if not handle:
                if ctypes.get_last_error() == 87:  # The member has already exited.
                    continue
                raise OSError(ctypes.get_last_error(), "Could not observe an owned process")
            belongs = wintypes.BOOL()
            if not self.kernel.IsProcessInJob(handle, self.handle, ctypes.byref(belongs)) or not belongs.value:
                self.kernel.CloseHandle(handle)
                raise RuntimeError("A listed process no longer has verifiable group ownership.")
            self.process_handles[pid] = handle

    def _handles_stopped(self):
        for handle in self.process_handles.values():
            result = self.kernel.WaitForSingleObject(handle, 0)
            if result == 258:
                return False
            if result != 0:
                raise OSError(self.ctypes.get_last_error(), "Could not confirm an owned process exit")
        return True

    def stop(self, timeout=15):
        if self.handle:
            self.remember_processes()
            if self._active_processes() and not self.kernel.TerminateJobObject(self.handle, 1):
                raise OSError(self.ctypes.get_last_error(), "Could not stop the owned worker group")
            # TerminateJobObject is asynchronous. The leader may already have
            # exited while husk or another owned descendant remains alive.
            deadline = time.monotonic() + timeout
            while self._active_processes() or not self._handles_stopped():
                self.remember_processes()
                if time.monotonic() >= deadline:
                    raise TimeoutError("The owned worker group has not confirmed that every process stopped.")
                time.sleep(0.02)
        elif os.name == "nt":
            if not self.quiescent:
                raise RuntimeError("Owned process-group quiescence is unavailable.")
        elif self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
        self.process.wait(timeout=timeout)
        self.quiescent = True
        self.verified_process_count = len(self.process_handles)

    def close(self):
        if self.handle:
            try:
                self.stop()
            finally:
                # Even on an unconfirmed timeout, closing retains the kernel's
                # kill-on-close protection. No terminal success is then emitted.
                self.kernel.CloseHandle(self.handle)
                self.handle = None
                for handle in self.process_handles.values():
                    self.kernel.CloseHandle(handle)
                self.process_handles.clear()


def _cancelled(operation, config):
    request_marker = Path(config["job_dir"]) / "cancel-request.json"
    if request_marker.exists():
        cancel = pkg.read_json(request_marker)
        if (cancel.get("request_id") == config["plan"]["request_id"] and
                cancel.get("plan_digest") == config["plan"]["digest"]):
            return True
    path = operation / "cancel.json"
    if not path.exists():
        return False
    cancel = pkg.read_json(path)
    return cancel.get("token") == config["token"] and cancel.get("plan_digest") == config["plan"]["digest"]


def supervise(config_path):
    config_path = Path(config_path).resolve()
    operation = config_path.parent
    config = pkg.read_json(config_path)
    plan = config["plan"]
    base = {"token": config["token"], "plan_digest": plan["digest"],
            "verified_frames": [], "outputs": []}
    process, tree = None, None
    try:
        pkg.validate_local_plan(plan)
        pkg.atomic_json(operation / "supervisor.json", {
            "token": config["token"], "plan_digest": plan["digest"],
            "identity": pkg.process_identity(os.getpid()) or {"pid": os.getpid(), "alive": None},
            "started_at": time.time()})
        if _cancelled(operation, config):
            pkg.atomic_json(operation / "status.json", {**base, "state": "cancelled",
                "note": "Cancelled before a native worker was launched.",
                "metadata": {"owned_processes_stopped": True}})
            return 0
        executable = Path(config["hfs"]) / "bin/hython.exe"
        command = [str(executable)]
        if config["phase"] == "render":
            command.append("--pdg")
        command.extend([str(Path(__file__).resolve()), "worker", str(config_path)])
        with (operation / "worker.stdout.log").open("wb") as out, (operation / "worker.stderr.log").open("wb") as err:
            process = subprocess.Popen(command, cwd=str(operation), env=dict(os.environ),
                                       stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                       start_new_session=os.name != "nt", close_fds=True)
            # The worker waits for this gate before loading a scene or doing work.
            tree = ProcessTree(process)
            pkg.atomic_json(operation / "admitted.json", {"token": config["token"]})
            started = time.monotonic()
            reason = None
            while process.poll() is None:
                tree.remember_processes()
                if _cancelled(operation, config):
                    reason = "cancelled"
                    tree.stop()
                    break
                if time.monotonic() - started > config["timeout_seconds"]:
                    reason = "timeout"
                    tree.stop()
                    break
                time.sleep(0.2)
            process.wait(timeout=15)
            # Close also kills any unexpected descendants before terminal receipt.
            tree.close()
            verified_process_count = tree.verified_process_count
            tree = None
        if reason == "cancelled" or _cancelled(operation, config):
            result = {"state": "cancelled", "note": "The owned preparation/render processes have stopped."}
        elif reason == "timeout":
            result = {"state": "failed", "note": "The owned job exceeded its runtime limit and its processes were stopped."}
        elif process.returncode != 0:
            result = {"state": "failed", "note": "The native worker failed. See the request's worker logs."}
            if (operation / "worker-result.json").is_file():
                worker = pkg.read_json(operation / "worker-result.json")
                result["note"] = worker.get("note", result["note"])
        else:
            result = pkg.read_json(operation / "worker-result.json")
            if result.get("state") not in ("prepared", "complete"):
                raise ValueError("The worker exited without a valid terminal result.")
        result.setdefault("metadata", {}).update({"native_returncode": process.returncode,
                                                  "worker_pid": process.pid,
                                                  "owned_processes_stopped": True,
                                                  "owned_active_processes": 0,
                                                  "owned_process_handles_verified": verified_process_count,
                                                  "native_elapsed_seconds": time.monotonic() - started,
                                                  "worker_log": str(operation / "worker.stdout.log")})
        pkg.atomic_json(operation / "status.json", {**base, **result})
        return 0
    except Exception as exc:
        cleanup_error = None
        if tree is not None:
            try:
                tree.close()
            except Exception as stop_error:
                cleanup_error = stop_error
        elif process is not None and process.poll() is None:
            # No gate was opened if group admission failed; the worker has no children.
            try:
                process.terminate()
                process.wait(timeout=15)
            except Exception as stop_error:
                cleanup_error = stop_error
        if cleanup_error is not None or (tree is not None and not tree.quiescent):
            result = {"state": "status_unavailable",
                "note": "The owned processes could not be confirmed stopped: " + str(cleanup_error or exc),
                "metadata": {"owned_processes_stopped": False}}
        else:
            result = {"state": "failed", "note": str(exc),
                      "metadata": {"owned_processes_stopped": True}}
        pkg.atomic_json(operation / "status.json", {**base, **result})
        traceback.print_exc()
        return 1


def _set(node, key, value):
    parm = node.parm(key)
    if parm is None:
        raise ValueError("Qualified native parameter is missing: " + node.path() + "/" + key)
    # Defaults may be expressions/keyframes: remove them before freezing values.
    parm.deleteAllKeyframes()
    parm.set(value)


def _asset_values(stage):
    """Include default and authored time samples; reject unresolved external assets."""
    from pxr import Usd
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if str(attr.GetTypeName()) not in ("asset", "asset[]"):
                continue
            for timecode in [Usd.TimeCode.Default()] + [Usd.TimeCode(t) for t in attr.GetTimeSamples()]:
                value = attr.Get(timecode)
                if value is None:
                    continue
                values = [value] if str(attr.GetTypeName()) == "asset" else list(value)
                yield attr, timecode, values


def _input_dependencies(stage):
    dependencies = {}
    for layer in stage.GetUsedLayers():
        if layer.realPath and Path(layer.realPath).is_file():
            dependencies[layer.realPath] = pkg.file_receipt(layer.realPath)
    for _, _, values in _asset_values(stage):
        for value in values:
            if not value.path or value.path.startswith("op:"):
                continue
            name = value.resolvedPath or value.path
            if not Path(name).is_file():
                raise ValueError("A source asset is missing or unsupported: " + value.path)
            dependencies[name] = pkg.file_receipt(name)
    return dependencies


def _localize_usd(usd_path, package_root, output_path, plan):
    from pxr import Gf, Sdf, Usd, UsdUtils
    stage = Usd.Stage.Open(str(usd_path))
    if not stage:
        raise ValueError("The exported USD could not be reopened.")
    settings_path = stage.GetMetadata("renderSettingsPrimPath")
    candidates = [prim for prim in stage.Traverse() if prim.GetTypeName() == "RenderSettings"]
    settings = stage.GetPrimAtPath(settings_path) if settings_path else None
    if not settings:
        if len(candidates) != 1:
            raise ValueError("The local profile requires one unambiguous render settings primitive.")
        settings = candidates[0]
    cameras = list(settings.GetRelationship("camera").GetTargets())
    if len(cameras) != 1 or stage.GetPrimAtPath(cameras[0]).GetTypeName() != "Camera":
        raise ValueError("The frozen source needs one valid render camera.")
    products = list(settings.GetRelationship("products").GetTargets())
    if len(products) != 1:
        raise ValueError("The current local profile supports one RGBA render product.")
    product = stage.GetPrimAtPath(products[0])
    if not product:
        raise ValueError("The render product is missing.")
    product.GetAttribute("productName").Set(str(output_path).replace("\\", "/"))
    settings.GetAttribute("resolution").Set(Gf.Vec2i(plan["width"], plan["height"]))
    for key in ("karma:global:samplesperpixel", "karma:global:pathtracedsamples"):
        attr = settings.CreateAttribute(key, Sdf.ValueTypeNames.Int)
        # A default alone does not override time samples in the exported layer.
        # Remove its value opinions before authoring the reviewed constant budget.
        attr.Clear()
        if not attr.Set(plan["samples"]) or attr.GetTimeSamples():
            raise ValueError("The reviewed sample budget could not be applied to every frame.")
    settings.CreateAttribute("karma:global:abortmissingtexture", Sdf.ValueTypeNames.Bool).Set(True)
    for attr, timecode, values in list(_asset_values(stage)):
        changed, updated = False, []
        for value in values:
            if not value.path:
                updated.append(value)
                continue
            if value.path.startswith("op:"):
                raise ValueError("The exported USD still depends on a live op: texture.")
            original = Path(value.resolvedPath or value.path)
            receipt = pkg.file_receipt(original)
            try:
                original.resolve().relative_to(package_root.resolve())
                target = original.resolve()
            except ValueError:
                target = package_root / "assets" / receipt["sha256"] / original.name
                if not target.exists():
                    pkg.frozen_copy(original, target, receipt["sha256"])
            relative = os.path.relpath(str(target), str(usd_path.parent)).replace("\\", "/")
            updated.append(Sdf.AssetPath(relative))
            changed = True
        if changed:
            attr.Set(updated[0] if str(attr.GetTypeName()) == "asset" else updated, timecode)
    stage.GetRootLayer().Save()
    _, assets, unresolved = UsdUtils.ComputeAllDependencies(str(usd_path))
    if unresolved:
        raise ValueError("The exported package has unresolved assets: " + ", ".join(map(str, unresolved)))
    for asset in assets:
        try:
            Path(asset).resolve().relative_to(package_root.resolve())
        except ValueError:
            raise ValueError("An exported asset still leaves the immutable package.")
    return {"camera": str(cameras[0]), "settings": str(settings.GetPath()),
            "product": str(products[0])}


def _admit_graph(output_node, render_nodes, expected):
    output_node.cookWorkItems(block=True, tops_only=True)
    output_node.generateStaticWorkItems(block=True)
    actual, detail = [], []
    for node in render_nodes:
        pdg_node = node.getPDGNode()
        if pdg_node is None or node.errors():
            raise ValueError("A required native render node could not generate work.")
        items = list(pdg_node.workItems)
        if len(items) != 1:
            raise ValueError("Exact frame admission failed: each frame node must generate one task.")
        frame = items[0].frame
        if frame != int(frame):
            raise ValueError("Exact frame admission failed: noninteger native frame.")
        actual.append(int(frame))
        detail.append({"node": node.path(), "work_item": items[0].name, "frame": int(frame)})
    if sorted(actual) != expected or len(actual) != len(expected):
        raise ValueError("Exact frame admission failed: native frame set differs from the prepared plan.")
    return detail


def prepare_native(config):
    import hou
    plan = config["plan"]
    root = Path(config["job_dir"])
    package_root = root / "package"
    package_root.mkdir(exist_ok=False)
    source = Path(plan["source_hip"])
    frozen = package_root / ("source" + source.suffix.lower())
    pkg.frozen_copy(source, frozen, plan["source_sha256"])
    hou.hipFile.load(str(frozen), suppress_save_prompt=True, ignore_load_warnings=True)
    # Preserve relative input-path semantics while preparing the frozen copy.
    hou.putenv("HIP", str(source.parent).replace("\\", "/"))
    source_node = hou.node(plan["source_node"])
    if source_node is None or source_node.type().category() != hou.lopNodeTypeCategory():
        raise ValueError("The saved source LOP does not exist in the frozen scene.")
    rop = hou.node("/out").createNode("usd", "synapse_farm_export")
    for key, value in {"loppath": source_node.path(), "savestyle": "flattenstage",
                       "savefilesfromdisk": 0, "trange": "normal"}.items():
        _set(rop, key, value)
    dependencies, outputs, frame_sources = {}, [], []
    camera_info = None
    for frame in plan["frames"]:
        hou.setFrame(frame)
        stage = source_node.stage()
        if stage is None or source_node.errors():
            raise ValueError("The source LOP did not produce an error-free USD stage.")
        current = _input_dependencies(stage)
        for key, value in current.items():
            if key in dependencies and dependencies[key] != value:
                raise ValueError("A source dependency changed during preparation.")
        dependencies.update(current)
        usd_path = package_root / ("frame_{:07d}.usda".format(frame))
        output_relative = "outputs/beauty.{:07d}.exr".format(frame)
        output_path = pkg.owned_path(root, output_relative)
        _set(rop, "lopoutput", str(usd_path).replace("\\", "/"))
        rop.render(frame_range=(frame, frame))
        if rop.errors():
            raise ValueError("Native USD export failed: " + " ".join(rop.errors()))
        info = _localize_usd(usd_path, package_root, output_path, plan)
        if camera_info is not None and camera_info != info:
            raise ValueError("The camera or render product changes between requested frames.")
        camera_info = info
        frame_sources.append({"frame": frame, "usd": str(usd_path.relative_to(root)).replace("\\", "/")})
        outputs.append({"frame": frame, "path": output_relative})
    for name, expected in dependencies.items():
        if pkg.file_receipt(name) != expected:
            raise ValueError("A source dependency changed while the package was prepared.")
    # The execution HIP contains only the native graph; it needs no artist scene.
    hou.hipFile.clear(suppress_save_prompt=True)
    net = hou.node("/obj").createNode("topnet", "synapse_render")
    local = next(n for n in net.children() if n.type().name() == "localscheduler")
    for key, value in {"maxprocsmenu": "1", "maxprocs": 1,
                       "local_usehoudinimaxthreads": 1, "local_houdinimaxthreads": 2,
                       "local_enabletimeout": 1, "local_maxtime": 60,
                       "local_handletimeout": 0, "local_echandleby": 0,
                       "local_maximumretries": 0, "local_requireswindow": 0,
                       "tempdirmenu": 0,
                       "pdg_workingdir": str(root / "work").replace("\\", "/")}.items():
        _set(local, key, value)
    render_nodes = []
    for source_info, output in zip(frame_sources, outputs):
        frame = source_info["frame"]
        node = net.createNode("usdrenderscene", "frame_" + str(frame).replace("-", "minus_"))
        values = {"sourcefilemode": 0, "sourcefilepath": str(root / source_info["usd"]).replace("\\", "/"),
                  "framerange": 1, "rangex": frame, "rangey": frame, "rangez": 1,
                  "outputsource": 0, "outputpath": str(root / output["path"]).replace("\\", "/"),
                  "resolution": 2, "resolutionspecificx": plan["width"], "resolutionspecificy": plan["height"],
                  "renderer": "BRAY_HdKarma", "usecamera": 1, "camera": camera_info["camera"]}
        for key, value in values.items():
            _set(node, key, value)
        node.setComment("Prepared frame {}. Immutable USD input; Karma CPU; 60 second limit.".format(frame))
        render_nodes.append(node)
    output_node = net.createNode("waitforall", "all_frames")
    for index, node in enumerate(render_nodes):
        output_node.setInput(index, node)
    output_node.setDisplayFlag(True)
    net.layoutChildren()
    admission = _admit_graph(output_node, render_nodes, plan["frames"])
    graph = package_root / "render_graph.hiplc"
    hou.hipFile.save(str(graph))
    manifest = {"schema_version": 1, "build": pkg.QUALIFIED_BUILD,
                "plan_digest": plan["digest"], "frames": plan["frames"],
                "graph": str(graph.relative_to(root)).replace("\\", "/"),
                "output_top": output_node.path(), "render_nodes": [n.path() for n in render_nodes],
                "outputs": outputs, "frame_sources": frame_sources, "admission": admission,
                "source_dependencies": dependencies, "source_sha256": plan["source_sha256"],
                "camera": camera_info["camera"], "render_settings": camera_info["settings"],
                "license_observed": str(hou.licenseCategory()),
                "file_paths": [str(path.relative_to(root)).replace("\\", "/") for path in package_root.rglob("*") if path.is_file()]}
    manifest = pkg.seal_manifest(root, manifest)
    return {"state": "prepared", "note": "Frozen USD assets and the native TOP graph are ready for review. Rendering has not started.",
                "metadata": {"package_digest": manifest["manifest_digest"], "graph_hip": str(graph),
                         "output_top": manifest["output_top"], "package_manifest": str(root / "package.json"),
                         "output_directory": str(root / "outputs"),
                         "camera": manifest["camera"], "license_observed": manifest["license_observed"]}}


def _verify_image(path, frame, plan):
    import OpenImageIO as oiio
    import numpy as np
    before = pkg.file_receipt(path)
    image = oiio.ImageInput.open(str(path))
    if image is None:
        raise ValueError("The rendered image could not be decoded: " + Path(path).name)
    try:
        spec = image.spec()
        if ((spec.width, spec.height) != (plan["width"], plan["height"]) or
                (spec.full_width, spec.full_height) != (plan["width"], plan["height"]) or
                (spec.x, spec.y, spec.full_x, spec.full_y) != (0, 0, 0, 0)):
            raise ValueError("The output data/display window differs from the reviewed resolution.")
        if list(spec.channelnames) != ["R", "G", "B", "A"]:
            raise ValueError("This local profile requires one RGBA EXR product.")
        pixels = image.read_image(0, 0, 0, spec.nchannels, oiio.FLOAT)
        if (pixels is None or tuple(pixels.shape) != (plan["height"], plan["width"], 4)
                or not bool(np.isfinite(pixels).all())):
            raise ValueError("The output failed full image decoding or numeric validation.")
        if image.seek_subimage(1, 0):
            raise ValueError("Multiple EXR parts require a separately qualified output profile.")
    finally:
        image.close()
    after = pkg.file_receipt(path)
    if before != after:
        raise ValueError("The image changed during verification.")
    return {"frame": frame, "path": str(Path(path).resolve()), **after,
            "width": plan["width"], "height": plan["height"], "verified": True}


def render_native(config):
    import hou
    from pdgjob import topcook
    plan, root = config["plan"], Path(config["job_dir"])
    manifest = pkg.verify_manifest(root, plan, config["manifest_digest"])
    for output in manifest["outputs"]:
        if pkg.owned_path(root, output["path"]).exists():
            raise ValueError("An output exists before rendering. This attempt cannot accept stale files.")
    hou.hipFile.load(str(pkg.owned_path(root, manifest["graph"])),
                     suppress_save_prompt=True, ignore_load_warnings=True)
    output_node = hou.node(manifest["output_top"])
    render_nodes = [hou.node(path) for path in manifest["render_nodes"]]
    if output_node is None or any(node is None for node in render_nodes):
        raise ValueError("The frozen graph is missing a required native node.")
    admission = _admit_graph(output_node, render_nodes, plan["frames"])
    failed, cooked = topcook.cookTopNode(manifest["output_top"], verbosity=2, print_logs=True)
    cooked.getPDGGraphContext().waitAllEvents()
    states = [{"node": node.path(), "frame": int(item.frame), "state": str(item.state)}
              for node in render_nodes for item in node.getPDGNode().workItems]
    pkg.atomic_json(root / "native-work-items.json", {"admission": admission, "states": states})
    if (failed or len(states) != len(plan["frames"]) or
            any(item["state"] != "workItemState.CookedSuccess" for item in states)):
        raise ValueError("Native TOP execution did not prove success for every required frame.")
    outputs = [_verify_image(pkg.owned_path(root, entry["path"]), entry["frame"], plan)
               for entry in manifest["outputs"]]
    # Recheck the frozen inputs as well as images before accepting their relationship.
    pkg.verify_manifest(root, plan, config["manifest_digest"])
    return {"state": "complete", "note": "Every requested frame passed native execution and full RGBA EXR verification.",
            "verified_frames": plan["frames"], "outputs": outputs,
            "verification": {"verified": True, "frames": plan["frames"], "decoder": "OpenImageIO full decode"}}


def worker(config_path):
    config_path = Path(config_path).resolve()
    operation, config = config_path.parent, pkg.read_json(config_path)
    try:
        gate = operation / "admitted.json"
        end = time.monotonic() + 30
        while not gate.exists():
            if time.monotonic() > end:
                raise ValueError("The detached supervisor did not admit this worker.")
            time.sleep(0.1)
        if pkg.read_json(gate).get("token") != config["token"]:
            raise ValueError("Invalid native process admission.")
        if _cancelled(operation, config):
            raise ValueError("Cancelled before native scene loading.")
        pkg.validate_local_plan(config["plan"])
        import hou
        if hou.isUIAvailable() or hou.applicationVersionString() != pkg.QUALIFIED_BUILD:
            raise ValueError("This worker requires a headless Houdini " + pkg.QUALIFIED_BUILD + " process.")
        result = prepare_native(config) if config["phase"] == "prepare" else render_native(config)
        pkg.atomic_json(operation / "worker-result.json", result)
        return 0
    except Exception as exc:
        pkg.atomic_json(operation / "worker-result.json", {"state": "failed", "note": str(exc)})
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("supervise", "worker"):
        raise SystemExit("Expected supervise|worker and an owned config path.")
    raise SystemExit(supervise(sys.argv[2]) if sys.argv[1] == "supervise" else worker(sys.argv[2]))
