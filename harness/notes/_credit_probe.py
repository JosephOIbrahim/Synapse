"""Is the Anthropic account funded now? C1-F2 said it was not.

C1 measured every token figure with a PROXY tokenizer because the account had no
credits - messages.create and messages.count_tokens both returned HTTP 400. That
put an asterisk on every number in the leg and on the README figures derived from
them.

This probe answers one question and prints no secret: does count_tokens work.
"""
import json, sys, urllib.request, urllib.error

KEY_NAMES = ("SYNAPSE_ANTHROPIC_KEY", "ANTHROPIC_API_KEY")


def key_from_env_file(path=".env"):
    try:
        for line in open(path, encoding="utf-8-sig", errors="replace"):
            line = line.strip()
            for name in KEY_NAMES:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None


key = key_from_env_file()
print("key present in .env:", bool(key))
if not key:
    sys.exit(1)

req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages/count_tokens",
    data=json.dumps({
        "model": "claude-sonnet-4-6",
        "messages": [{"role": "user", "content": "token count probe"}],
    }).encode(),
    headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
)

try:
    resp = json.load(urllib.request.urlopen(req, timeout=30))
    print("count_tokens: OK ->", resp)
    print("VERDICT: the account is funded. C1's proxy-tokenizer asterisk can be removed.")
    sys.exit(0)
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", "replace")
    print("count_tokens: HTTP", e.code)
    print("body:", body[:300])
    print("VERDICT: still blocked - C1-F2 stands.")
    sys.exit(1)
except Exception as e:
    print("count_tokens: FAILED", type(e).__name__, str(e)[:120])
    sys.exit(1)
