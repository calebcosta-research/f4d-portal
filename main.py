"""F4D Results Reporting — Streamlit entry point.

The app logic lives in the ``f4d`` package; this file only configures the
page and launches the router. Run with: ``streamlit run main.py``.
"""
import os
import sys

import streamlit as st

# Must be the first Streamlit call.
st.set_page_config(page_title="F4D Results Reporting", layout="centered")

# Make this app's own directory importable so the `f4d` package resolves no
# matter what working directory the host uses. Posit Connect runs the entry
# point without the app directory on sys.path, which otherwise breaks
# `from f4d.shell import main` ("No module named 'f4d'").
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from f4d import telemetry

# Start Application Insights, once per process -- a no-op without a
# connection string. Before the app imports, so its outbound calls are
# instrumented.
telemetry.setup()

from f4d.shell import main
from connection import close_run_sessions

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Report anything unhandled before Streamlit displays it. Streamlit's
        # own rerun/stop signals derive from BaseException, so they pass
        # straight through.
        telemetry.log.exception("unhandled error")
        raise
    finally:
        # Return every database connection this run opened -- including when
        # the run ends early with Streamlit's rerun or stop signal.
        close_run_sessions()
