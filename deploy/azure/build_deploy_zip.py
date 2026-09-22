"""Build app.zip for Azure App Service deployment.

Run from anywhere; paths are resolved relative to this file:

    ./venv/Scripts/python.exe deploy/azure/build_deploy_zip.py [git-ref]

Then deploy the zip with (the `config-zip` form matters -- see the README):

    az webapp deployment source config-zip -g <rg> -n <app> --src app.zip

It packs the *committed* files at a git ref (default HEAD), never the working
tree, so what ships is exactly what's in git: no uncommitted edits, local
databases, logs or stray generated files.

What goes in: the running application -- main.py, model.py, connection.py,
superadmin.py, the f4d package, .streamlit/config.toml -- and the README. What
stays out: the Posit Connect deployment files, the dev-only seeds, docs, this
whole deploy tree (the ops scripts run from a workstation, not inside the App
Service), and workstation tooling the app never imports: the batch importer
and the .env.example template. Less shipped is less for a security scan to read.

requirements.txt is substituted: the zip gets deploy/azure/requirements.txt
(the App Service dependency set) in place of the repo-root one, which is the
Posit Connect set and pins pyodbc against a system ODBC driver.
"""
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REF = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
OUT = os.path.join(ROOT, "app.zip")

# Top-level directories that belong to another system, or to no system.
EXCLUDE_TOP_DIRS = {"deploy", "dev", "docs"}
# Posit Connect's bundle files, git's own file, and workstation tooling.
EXCLUDE_FILES = {"manifest.json", ".rscignore", ".gitignore", ".env.example", "batch_import.py"}
EXCLUDE_PREFIXES = ("f4d/batch/",)
EXCLUDE_EXT = {".db", ".log", ".sqlite3", ".ps1", ".zip"}


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, check=True).stdout


def ships(path):
    return (path.split("/")[0] not in EXCLUDE_TOP_DIRS
            and path not in EXCLUDE_FILES
            and not path.startswith(EXCLUDE_PREFIXES)
            and os.path.splitext(path)[1] not in EXCLUDE_EXT)


tracked = git("ls-tree", "-r", "--name-only", REF).decode("utf-8").split("\n")
files = sorted(p for p in tracked if p and ships(p))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for path in files:
        source = "deploy/azure/requirements.txt" if path == "requirements.txt" else path
        z.writestr(path, git("show", f"{REF}:{source}"))

print("wrote:", OUT)
print("from:", REF, git("rev-parse", "--short", REF).decode().strip())
print("zipped files:", len(files))
