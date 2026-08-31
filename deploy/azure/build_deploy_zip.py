"""Build app.zip for Azure App Service deployment.

Run from anywhere; paths are resolved relative to this file:

    ./venv/Scripts/python.exe deploy/azure/build_deploy_zip.py

Then deploy the zip with (the `config-zip` form matters -- see the README):

    az webapp deployment source config-zip -g <rg> -n <app> --src app.zip

What goes in: the shared application at the repo root (main.py, model.py,
connection.py, the f4d package, .streamlit/config.toml). What stays out: the
local venv, git, caches, the local SQLite DB and logs, the Posit Connect
deployment files, the dev-only seeds, and this whole deploy tree -- the Azure
ops scripts are run from a workstation against the database, not from inside
the App Service.

requirements.txt is substituted: the zip gets deploy/azure/requirements.txt
(the App Service dependency set) in place of the repo-root one, which is the
Posit Connect set and pins pyodbc -- that wheel installs on Linux but has no
system ODBC driver behind it in the stock App Service image.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

# Directories never included, matched by name at any depth.
EXCLUDE_DIRS = {"venv", ".git", "__pycache__", ".vscode", "exports"}
# Top-level directories that belong to another system (or to no system).
EXCLUDE_TOP_DIRS = {"deploy", "dev", "docs"}
EXCLUDE_EXT = {".db", ".log", ".sqlite3", ".ps1", ".zip"}
# manifest.json and .rscignore describe the Posit Connect bundle; app.zip is
# the output; .env is local secrets.
EXCLUDE_FILES = {".env", "app.zip", "manifest.json", ".rscignore"}

OUT = os.path.join(ROOT, "app.zip")
REQUIREMENTS = os.path.join(HERE, "requirements.txt")

with open(REQUIREMENTS, encoding="utf-8") as fh:
    azure_requirements = fh.read()

n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT).replace(os.sep, "/")
        if rel_dir == ".":
            dirnames[:] = [d for d in dirnames
                           if d not in EXCLUDE_DIRS and d not in EXCLUDE_TOP_DIRS]
        else:
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if os.path.splitext(f)[1] in EXCLUDE_EXT or f in EXCLUDE_FILES:
                continue
            full = os.path.join(dirpath, f)
            arc = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if arc == "requirements.txt":
                z.writestr("requirements.txt", azure_requirements)
            else:
                z.write(full, arc)
            n += 1

print("wrote:", OUT)
print("zipped files:", n)
