"""Batch import for the F4D Results Reporting portal.

Two use cases share one engine (see core.py):
  * one-time historical migration  -> run batch_import.py from the command line
  * ongoing in-app bulk upload      -> import core.import_rows from a Streamlit page

The engine writes into the same EAV ``grant_info_long`` table the app reads,
using the exact field names and value encodings the live app expects, so
imported data is indistinguishable from data typed in through the portal.
"""
