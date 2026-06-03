"""F4D Results Reporting — Streamlit entry point.

The app logic lives in the ``f4d`` package; this file only configures the
page and launches the router. Run with: ``streamlit run main.py``.
"""
import streamlit as st

# Must be the first Streamlit call.
st.set_page_config(page_title="F4D Results Reporting", layout="centered")

from f4d.shell import main

if __name__ == "__main__":
    main()
