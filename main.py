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

from f4d.shell import main

if __name__ == "__main__":
    main()
