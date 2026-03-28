# ==============================================================
# ANU QRNG - Live Hex Stream
# Script DAT for TouchDesigner
#
# Setup:
#   1. Create a Script DAT in your project
#   2. Paste this script
#   3. Create a Text DAT named "qrng_output" to receive values
#   4. (Optional) Create a Table DAT named "qrng_table" for history log
#   5. The API key is read from environment variable ANU_API_KEY
# ==============================================================

import urllib.request
import urllib.parse
import json
import threading
import time
import os
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# ---- Configuration ----
ENDPOINT    = "https://api.quantumnumbers.anu.edu.au"
API_KEY     = parent().par.Apikey
MAX_HISTORY = parent().par.Maxhistory
INTERVAL    = parent().par.Interval
BATCH_SIZE  = parent().par.Batchsize


# ---- Internal state ----
_hex_history = []
_running     = False
_thread      = None
_lock        = threading.Lock()


# ──────────────────────────────────────────────
# Polling loop (background thread)
# ──────────────────────────────────────────────
def _poll_loop():
    global _hex_history, _running

    while _running:
        try:
            params = urllib.parse.urlencode({
                'length': BATCH_SIZE,
                'type':   'hex16',
                'size':   2
            })
            url = f"{ENDPOINT}?{params}"
            req = urllib.request.Request(
                url,
                headers={'x-api-key': API_KEY}
            )
            response = urllib.request.urlopen(req, timeout=10)
            data     = json.loads(response.read().decode('utf-8'))
            values   = data.get('data', [])

            if values:
                with _lock:
                    for v in values:
                        _hex_history.insert(0, v)
                    if len(_hex_history) > MAX_HISTORY:
                        _hex_history = _hex_history[:MAX_HISTORY]

                run("mod('qrng_script')._update_operators()", delayFrames=0)

        except Exception as e:
            print(f"QRNG error: {e}")

        time.sleep(INTERVAL)


# ──────────────────────────────────────────────
# TouchDesigner operator updates
# ──────────────────────────────────────────────
def _update_operators():
    with _lock:
        values = list(_hex_history)

    if not values:
        return

    latest_val = values[0]

    # Text DAT: latest value
    try:
        op("qrng_output_text").text = latest_val
    except Exception:
        pass

    # Table DAT: full history
    try:
        t = op("qrng_table")
        t.clear()
        t.appendRow(["hex", "float"])
        for v in values:
            f = int(v, 16) / (16 ** len(v) - 1)
            t.appendRow([v, f"{f:.6f}"])
    except Exception:
        pass

    # Script CHOP: normalized float channel (if present)
    try:
        f = int(latest_val, 16) / (16 ** len(latest_val) - 1)
        op("qrng_chop")['qrng'][0] = f
    except Exception:
        pass


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────
def start():
    """Start the quantum stream. Call from a Button or Execute DAT."""
    global _running, _thread, INTERVAL, BATCH_SIZE, API_KEY
    if _running:
        print("QRNG: already running.")
        return
    
    # Lire les params du composant parent au moment du start
    try:
        parent_op = op('/project1/QRNG_ANU')
        API_KEY    = parent_op.par.Apikey.val
        INTERVAL   = parent_op.par.Interval.val
        BATCH_SIZE = int(parent_op.par.Batchsize.val)
    except:
        pass  # garde les valeurs par défaut si les params n'existent pas
    
    if not API_KEY:
        print("QRNG: API key not set.")
        return
    
    _running = True
    _thread  = threading.Thread(target=_poll_loop, daemon=True)
    _thread.start()
    print(f"QRNG: started (interval {int(INTERVAL * 1000)} ms, batch {BATCH_SIZE}).")


def stop():
    """Stop the quantum stream."""
    global _running
    _running = False
    print("QRNG: stopped.")


def latest():
    """Return the latest hex value (str or None)."""
    with _lock:
        return _hex_history[0] if _hex_history else None


def latest_float():
    """Return the latest value normalized to 0.0–1.0."""
    v = latest()
    if v:
        return int(v, 16) / (16 ** len(v) - 1)
    return None


def randint(min_val, max_val):
    """Return a quantum random integer in [min_val, max_val]."""
    f = latest_float()
    if f is not None:
        return min_val + int(f * (max_val - min_val + 1))
    return None


def history():
    """Return the full history list (most recent first)."""
    with _lock:
        return list(_hex_history)


def clear():
    """Clear the history."""
    global _hex_history
    with _lock:
        _hex_history = []
    print("QRNG: history cleared.")


# ──────────────────────────────────────────────
# Auto-start on project load
# ──────────────────────────────────────────────
start()
