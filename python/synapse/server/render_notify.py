"""
Synapse Render Notifications

Three notification channels, zero new pip dependencies:
1. Windows Toast -- PowerShell [Windows.UI.Notifications]
2. Report File  -- Markdown to $HIP/.synapse/render_reports/
3. WebSocket Push -- Broadcast to connected MCP clients

Notification triggers:
- Batch complete: always toast + report
- Persistent failure: immediate toast
- Milestones (25/50/75%): optional progress toast
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("synapse.render_farm")


# =========================================================================
# Data structures
# =========================================================================

@dataclass
class FrameResult:
    """Result of rendering and validating a single frame."""
    frame: int
    success: bool
    render_time: float = 0.0
    validate_time: float = 0.0
    retries: int = 0
    issues: List[str] = field(default_factory=list)
    fixes_applied: List[str] = field(default_factory=list)
    image_path: str = ""
    error: str = ""


@dataclass
class BatchReport:
    """Summary of an entire render sequence batch."""
    start_frame: int
    end_frame: int
    total_frames: int = 0
    successful_frames: int = 0
    failed_frames: int = 0
    total_render_time: float = 0.0
    total_wall_time: float = 0.0
    rop_path: str = ""
    scene_tags: List[str] = field(default_factory=list)
    frame_results: List[FrameResult] = field(default_factory=list)
    settings_used: Dict = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.successful_frames / self.total_frames

    def to_dict(self) -> Dict:
        return {
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "total_frames": self.total_frames,
            "successful_frames": self.successful_frames,
            "failed_frames": self.failed_frames,
            "success_rate": round(self.success_rate, 3),
            "total_render_time": round(self.total_render_time, 2),
            "total_wall_time": round(self.total_wall_time, 2),
            "rop_path": self.rop_path,
            "scene_tags": self.scene_tags,
            "settings_used": self.settings_used,
            "frame_results": [
                {
                    "frame": fr.frame,
                    "success": fr.success,
                    "render_time": round(fr.render_time, 2),
                    "retries": fr.retries,
                    "issues": fr.issues,
                    "fixes_applied": fr.fixes_applied,
                    "image_path": fr.image_path,
                    "error": fr.error,
                }
                for fr in self.frame_results
            ],
        }


# =========================================================================
# Windows Toast Notification
# =========================================================================

_TOAST_PS_TEMPLATE = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>{title}</text>
            <text>{body}</text>
        </binding>
    </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Synapse").Show($toast)
"""


def send_toast(title: str, body: str) -> bool:
    """Send a Windows toast notification via PowerShell.

    Returns True if the toast was sent successfully, False otherwise.
    Fails silently on non-Windows or if PowerShell is unavailable.
    """
    if os.name != "nt":
        logger.debug("Toast notifications only supported on Windows")
        return False

    # Sanitize for XML/PowerShell
    safe_title = title.replace('"', "'").replace("<", "&lt;").replace(">", "&gt;")
    safe_body = body.replace('"', "'").replace("<", "&lt;").replace(">", "&gt;")

    ps_script = _TOAST_PS_TEMPLATE.format(title=safe_title, body=safe_body)

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            logger.debug("Toast PowerShell failed: %s", result.stderr[:200])
            return False
        return True
    except Exception:
        logger.debug("Toast notification failed", exc_info=True)
        return False


# =========================================================================
# Report File (Markdown)
# =========================================================================

def write_report(report: BatchReport, output_dir: str) -> str:
    """Write a Markdown render report to the output directory.

    Args:
        report: BatchReport with frame results.
        output_dir: Directory path (e.g. "$HIP/.synapse/render_reports/").

    Returns:
        Path to the written report file.
    """
    os.makedirs(output_dir, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"render_report_{report.start_frame}-{report.end_frame}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    lines = [
        f"# Render Report: Frames {report.start_frame}-{report.end_frame}",
        "",
        f"**ROP:** `{report.rop_path}`",
        f"**Frames:** {report.successful_frames}/{report.total_frames} successful "
        f"({report.success_rate:.0%})",
        f"**Render Time:** {report.total_render_time:.1f}s "
        f"(wall: {report.total_wall_time:.1f}s)",
        f"**Scene Tags:** {', '.join(report.scene_tags) or 'none'}",
        "",
        "## Settings Used",
        "",
    ]

    if report.settings_used:
        for key in sorted(report.settings_used.keys()):
            lines.append(f"- **{key}:** {report.settings_used[key]}")
    else:
        lines.append("- (default settings)")

    lines.extend(["", "## Frame Results", ""])
    lines.append("| Frame | Status | Render Time | Retries | Issues | Fixes |")
    lines.append("|-------|--------|-------------|---------|--------|-------|")

    for fr in report.frame_results:
        status = "OK" if fr.success else "FAIL"
        issues = ", ".join(fr.issues) if fr.issues else "-"
        fixes = ", ".join(fr.fixes_applied) if fr.fixes_applied else "-"
        lines.append(
            f"| {fr.frame} | {status} | {fr.render_time:.1f}s | "
            f"{fr.retries} | {issues} | {fixes} |"
        )

    # Failed frames detail
    failed = [fr for fr in report.frame_results if not fr.success]
    if failed:
        lines.extend(["", "## Failed Frames", ""])
        for fr in failed:
            lines.append(f"### Frame {fr.frame}")
            lines.append(f"- **Error:** {fr.error or 'Validation failed after max retries'}")
            lines.append(f"- **Issues:** {', '.join(fr.issues)}")
            lines.append(f"- **Retries:** {fr.retries}")
            lines.append("")

    lines.extend([
        "",
        "---",
        f"*Generated by Synapse Render Farm at {time.strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
    ])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


# =========================================================================
# WebSocket Push
# =========================================================================

def build_progress_event(
    frame: int,
    total_frames: int,
    status: str,
    details: Optional[Dict] = None,
) -> Dict:
    """Build a render progress event for WebSocket broadcast.

    Args:
        frame: Current frame number.
        total_frames: Total frames in the sequence.
        status: One of "rendering", "validating", "fixing", "complete", "failed".
        details: Optional extra data.

    Returns:
        Event dict suitable for JSON serialization and WebSocket send.
    """
    event = {
        "type": "render_farm_progress",
        "frame": frame,
        "total_frames": total_frames,
        "progress": round(frame / max(total_frames, 1), 3),
        "status": status,
        "timestamp": time.time(),
    }
    if details:
        event["details"] = details
    return event


# =========================================================================
# Notification orchestration
# =========================================================================

def notify_batch_complete(report: BatchReport, output_dir: str) -> Dict:
    """Send all notifications for a completed batch.

    Args:
        report: The completed batch report.
        output_dir: Directory for the markdown report.

    Returns:
        Dict summarizing notification results.
    """
    results = {}

    # Write report file (always)
    try:
        report_path = write_report(report, output_dir)
        results["report_path"] = report_path
    except Exception as e:
        results["report_error"] = str(e)

    # Toast notification
    if report.failed_frames > 0:
        title = "Synapse Render Farm"
        body = (
            f"Batch complete: {report.successful_frames}/{report.total_frames} frames OK. "
            f"{report.failed_frames} failed."
        )
    else:
        title = "Synapse Render Farm"
        body = (
            f"All {report.total_frames} frames rendered successfully! "
            f"Total time: {report.total_wall_time:.0f}s"
        )
    results["toast_sent"] = send_toast(title, body)

    return results


def notify_persistent_failure(frame: int, issue: str, retries: int) -> bool:
    """Send immediate toast when a frame exhausts all retries."""
    return send_toast(
        "Synapse: Render Issue",
        f"Frame {frame} failed after {retries} retries. Issue: {issue}",
    )
