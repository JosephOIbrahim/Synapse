"""Control for the Slack-style dialogue presentation.

Measured before the change: the only thing separating the two voices was tone -
#DEDEDE for the human, #C5C5C5 for the agent, plus a 2px rule on the human side.
Twenty-five points of grey on a dim panel is not a speaker signal; the reader has
to infer, every message.

Slack's actual anatomy is a NAME at the head of a group, the time beside it, and
NOTHING repeated on continuations. That last part is the whole property - a label
on every message is a chat log, not Slack.

Asserts both directions.
"""
import re, sys
sys.path.insert(0, "python")

from synapse.panel.message_formatter import (
    format_user_message, format_synapse_message, format_system_message)

ok = True


def check(label, cond):
    global ok
    print("  %-46s %s" % (label, "PASS" if cond else "FAIL"))
    if not cond:
        ok = False


print("=" * 66)
print("GROUP HEAD - the speaker must be named")
print("=" * 66)
u = format_user_message("build a lighting rig", grouped=False, timestamp="16:42")
s = format_synapse_message("Done - three lights wired.", grouped=False,
                           timestamp="16:42", signed="GLM 5.2")
check("user head carries YOU", "YOU" in u)
check("user head carries the time", "16:42" in u)
check("synapse head carries SYNAPSE", "SYNAPSE" in s)
check("synapse head carries the time", "16:42" in s)

print()
print("=" * 66)
print("CONTINUATION - nothing repeated (this is what makes it Slack)")
print("=" * 66)
u2 = format_user_message("and a camera", grouped=True, timestamp="16:43")
s2 = format_synapse_message("Camera added.", grouped=True, timestamp="16:43")
check("grouped user has NO label", "YOU" not in u2)
check("grouped user has NO timestamp", "16:43" not in u2)
check("grouped synapse has NO label", "SYNAPSE" not in s2)
check("grouped synapse has NO timestamp", "16:43" not in s2)

print()
print("=" * 66)
print("THE LABEL IS CHROME, NOT CONTENT")
print("=" * 66)
m = re.search(r'font-family:[^;]*(Consolas|monospace)[^"]*"?[^>]*>YOU', u)
check("label is mono", bool(m) or "monospace" in u.split("YOU")[0][-220:])
check("label is letterspaced", "letter-spacing" in u.split("YOU")[0][-220:])
check("body text still bright", "#DEDEDE" in u.upper() or "DEDEDE" in u.upper())
check("system message is NOT a speaker",
      "YOU" not in format_system_message("Bridge running on :9999"))

print()
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
