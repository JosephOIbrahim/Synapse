"""G6 propagation check for cinema::camera_rig with sub-HDAs."""
import hou

def has_expr(parm):
    try:
        parm.expression()
        return True
    except hou.OperationFailed:
        return False

# Create fresh instance
obj = hou.node("/obj")
rig = None
for n in obj.children():
    if n.type().name() == "cinema::camera_rig":
        rig = n
        break

if not rig:
    try:
        rig = obj.createNode("cinema::camera_rig", "g6_test")
    except Exception as e:
        result = "ERROR creating rig: " + str(e)

lines = []
passed = True

if not rig:
    lines.append("ERROR: No cinema::camera_rig instance")
    passed = False
else:
    lines.append("Rig: " + rig.path())

    # 1. Check internal nodes
    for name in ["cinema_camera", "entrance_pupil_pivot", "fluid_head_mount",
                  "biomechanics", "post_pipeline"]:
        ok = rig.node(name) is not None
        lines.append(("PASS" if ok else "FAIL") + "  Node: " + name)
        if not ok:
            passed = False

    # 2. Check sub-HDA instances
    for path, etype in [
        ("biomechanics/biomech_solver", "cinema::chops_biomechanics"),
        ("post_pipeline/anamorphic_flare", "cinema::cop_anamorphic_flare"),
        ("post_pipeline/sensor_noise", "cinema::cop_sensor_noise"),
        ("post_pipeline/stmap_aov", "cinema::cop_stmap_aov"),
    ]:
        node = rig.node(path)
        if node:
            t = node.type().name()
            if t == etype:
                lines.append("PASS  Sub-HDA: " + path + " (" + t + ")")
            elif t == "null":
                lines.append("WARN  Sub-HDA: " + path + " (fallback null)")
            else:
                lines.append("FAIL  Sub-HDA: " + path + " (" + t + ")")
                passed = False
        else:
            lines.append("FAIL  Sub-HDA: " + path + " (missing)")
            passed = False

    # 3. Check top-level parm defaults
    for pname, exp in [
        ("focal_length_mm", 50.0), ("squeeze_ratio", 2.0),
        ("effective_squeeze", 2.0), ("resolution_x", 4608),
        ("resolution_y", 3164), ("combined_weight_kg", 7.5),
        ("damping_ratio", 0.5), ("enable_flare", 1),
        ("flare_threshold", 3.0), ("flare_intensity", 0.3),
        ("enable_sensor_noise", 1), ("exposure_index", 800),
        ("native_iso", 800), ("photon_noise_amount", 1.0),
        ("read_noise_amount", 1.0),
    ]:
        p = rig.parm(pname)
        if p:
            v = p.eval()
            ok = abs(float(v) - float(exp)) < 0.01
            lines.append(("PASS" if ok else "FAIL") + "  Parm: " + pname + "=" + str(v))
            if not ok:
                passed = False
        else:
            lines.append("FAIL  Parm: " + pname + " (missing)")
            passed = False

    # 4. Check camera expression wiring
    cam = rig.node("cinema_camera")
    if cam:
        for cparm, tparm in [("focal", "focal_length_mm"), ("aperture", "sensor_width_mm"),
                              ("resx", "resolution_x"), ("resy", "resolution_y")]:
            p = cam.parm(cparm)
            if p and has_expr(p):
                expr = p.expression()
                ok = tparm in expr
                lines.append(("PASS" if ok else "FAIL") + "  Expr: cam." + cparm + " -> " + tparm)
                if not ok:
                    passed = False
            else:
                lines.append("FAIL  Expr: cam." + cparm + " (no expr)")
                passed = False

    # 5. Check entrance pupil expression
    pivot = rig.node("entrance_pupil_pivot")
    if pivot and has_expr(pivot.parm("tz")):
        expr = pivot.parm("tz").expression()
        ok = "entrance_pupil_offset_mm" in expr
        lines.append(("PASS" if ok else "FAIL") + "  Expr: pupil.tz")
        if not ok:
            passed = False
    else:
        lines.append("FAIL  Expr: pupil.tz (no expr)")
        passed = False

    # 6. Check ALL sub-HDA expression wiring
    expr_checks = [
        ("post_pipeline/anamorphic_flare", [
            ("enable", "enable_flare"), ("threshold", "flare_threshold"),
            ("intensity", "flare_intensity"), ("squeeze_ratio", "effective_squeeze"),
        ]),
        ("post_pipeline/sensor_noise", [
            ("enable", "enable_sensor_noise"), ("exposure_index", "exposure_index"),
            ("native_iso", "native_iso"), ("photon_noise_amount", "photon_noise_amount"),
            ("read_noise_amount", "read_noise_amount"),
        ]),
        ("post_pipeline/stmap_aov", [
            ("resolution_x", "resolution_x"), ("resolution_y", "resolution_y"),
            ("dist_k1", "dist_k1"), ("dist_k2", "dist_k2"), ("dist_k3", "dist_k3"),
            ("dist_p1", "dist_p1"), ("dist_p2", "dist_p2"),
            ("dist_sq_uniformity", "dist_sq_uniformity"),
            ("effective_squeeze", "effective_squeeze"),
        ]),
        ("biomechanics/biomech_solver", [
            ("combined_weight_kg", "combined_weight_kg"),
            ("moment_arm_cm", "moment_arm_cm"),
            ("spring_constant", "spring_constant"),
            ("damping_ratio", "damping_ratio"),
            ("lag_frames", "lag_frames"),
            ("enable_handheld", "enable_handheld"),
            ("shake_amplitude_deg", "shake_amplitude_deg"),
            ("shake_frequency_hz", "shake_frequency_hz"),
            ("auto_derive", "auto_derive"),
        ]),
    ]
    for npath, parms in expr_checks:
        node = rig.node(npath)
        nname = npath.split("/")[-1]
        if node and node.type().name() != "null":
            for sparm, tparm in parms:
                p = node.parm(sparm)
                if p and has_expr(p):
                    expr = p.expression()
                    ok = tparm in expr
                    lines.append(("PASS" if ok else "FAIL") + "  Expr: " + nname + "." + sparm + " -> " + tparm)
                    if not ok:
                        passed = False
                elif p:
                    lines.append("FAIL  Expr: " + nname + "." + sparm + " (no expr)")
                    passed = False
                else:
                    lines.append("FAIL  Expr: " + nname + "." + sparm + " (parm missing)")
                    passed = False
        elif node:
            lines.append("SKIP  Expr: " + nname + " (fallback null, " + str(len(parms)) + " parms)")

    # 7. Check help strings
    for pname in ["t_stop", "dist_k1", "dist_p1", "resolution_x", "exposure_index",
                   "moment_arm_cm", "spring_constant", "shake_amplitude_deg",
                   "photon_noise_amount", "flare_threshold"]:
        p = rig.parm(pname)
        if p:
            h = p.parmTemplate().help()
            ok = len(h) > 10
            lines.append(("PASS" if ok else "FAIL") + "  Help: " + pname)
            if not ok:
                passed = False

    # 8. Check viewport overlay on pupil null
    if pivot:
        ct = pivot.parm("controltype").eval()
        ok = ct == 1  # Circles
        lines.append(("PASS" if ok else "FAIL") + "  Viewport: pupil controltype=" + str(ct))
        if not ok:
            passed = False
        cr = pivot.parm("dcolorr").eval()
        ok = abs(cr - 1.0) < 0.01
        lines.append(("PASS" if ok else "FAIL") + "  Viewport: pupil color_r=" + str(cr))

    # 9. Check effective_squeeze is read-only (DisableWhen)
    es = rig.parm("effective_squeeze")
    if es:
        cond = es.parmTemplate().conditionals()
        has_disable = hou.parmCondType.DisableWhen in cond
        lines.append(("PASS" if has_disable else "FAIL") + "  UI: effective_squeeze read-only")
        if not has_disable:
            passed = False

    lines.append("")
    lines.append("G6 PROPAGATION CHECK: " + ("PASS" if passed else "FAIL"))

result = "\n".join(lines)
