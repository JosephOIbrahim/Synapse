"""
Spike 0 — SDK Import Gate

Purpose: Prove the Claude Agent SDK imports cleanly in SideFX Houdini's
Python interpreter (hython) and completes an async round-trip to Anthropic
without asyncio/httpx/anyio friction.

This is the cheapest possible proof that the inside-out architecture has
legs. ~10 minutes. If this fails, the entire Sprint 3 plan stalls here
until the failure is understood.

Run:
    hython spikes/spike_0.py

Expected output on pass:
    [Spike 0] Host: SideFX Houdini 21.0.631 (hython)
    [Spike 0] SDK: Anthropic imported cleanly.
    [Spike 0] Auth: Retrieved from hou.secure   (or from env)
    [Spike 0] Yielding to network I/O (testing hython asyncio loop)...

    [Spike 0] SUCCESS! Agent response:
     > HYTHON_ALIVE

Known failure modes:
  1. Hang or NotImplementedError — ProactorEventLoop collision with
     httpx/anyio on Python 3.11 Windows. Uncomment the
     WindowsSelectorEventLoopPolicy line near the bottom.
  2. ImportError on 'anthropic' — install via: hython -m pip install anthropic
  3. Anything else — capture full stack trace for staged Gemini prompt.
"""
import sys
import os
import asyncio


# 1. Host Gate — confirm we're actually inside hython, not stock Python
try:
    import hou
    print(f"[Spike 0] Host: SideFX Houdini {hou.applicationVersionString()} (hython)")
except ImportError:
    print("[Spike 0] FATAL: Not running inside hython.")
    sys.exit(1)


# 2. Dependency Gate — confirm the Agent SDK can be imported
try:
    from anthropic import AsyncAnthropic
    print("[Spike 0] SDK: Anthropic imported cleanly.")
except ImportError as e:
    print(f"[Spike 0] FATAL: Import failed - {e}")
    print("[Spike 0] Install with: hython -m pip install anthropic")
    sys.exit(1)


async def run_spike():
    # 3. Auth Gate — env var first, then hou.secure (Windows Credential Manager)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    source = "env"

    if not api_key:
        try:
            api_key = hou.secure.password('synapse_anthropic')
            if api_key:
                source = "hou.secure"
                print("[Spike 0] Auth: Retrieved from hou.secure")
        except Exception:
            pass

    if api_key and source == "env":
        print("[Spike 0] Auth: Retrieved from ANTHROPIC_API_KEY env var")

    if not api_key:
        print("[Spike 0] SKIP: API key missing from env and hou.secure.")
        print("[Spike 0]       Bypassing network test.")
        print("[Spike 0]       To test round-trip, set ANTHROPIC_API_KEY or:")
        print("[Spike 0]         hou.secure.setPassword('synapse_anthropic', 'sk-ant-...')")
        return

    client = AsyncAnthropic(api_key=api_key)
    print("[Spike 0] Yielding to network I/O (testing hython asyncio loop)...")

    try:
        # Cheap model for raw physics check — not representative of production model choice
        response = await client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": (
                    "I am executing inside SideFX Houdini's Python interpreter (hython). "
                    "Reply with the exact string: HYTHON_ALIVE"
                )
            }]
        )
        print(f"\n[Spike 0] SUCCESS! Agent response:")
        print(f" > {response.content[0].text}")
    except Exception as e:
        print(f"\n[Spike 0] FAIL! Async/Network exception: {type(e).__name__} - {e}")
        sys.exit(1)


if __name__ == "__main__":
    # ---------------------------------------------------------------------
    # THE TRAP DOOR
    # ---------------------------------------------------------------------
    # Python 3.11 on Windows defaults to ProactorEventLoop. This frequently
    # clashes with DCC C++ host loops and with httpx/anyio (the async HTTP
    # stack the Anthropic SDK depends on).
    #
    # If the script hangs or throws asyncio.NotImplementedError, uncomment
    # the line below for your first remediation. If the selector policy
    # fixes it, this fix becomes permanent in the daemon bootstrap
    # (synapse.host.daemon) at Spike 2.
    #
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # ---------------------------------------------------------------------

    try:
        asyncio.run(run_spike())
    except Exception as e:
        print(f"[Spike 0] FATAL Event Loop Failure: {type(e).__name__} - {e}")
        sys.exit(1)
