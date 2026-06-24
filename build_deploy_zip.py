"""Build app.zip for Azure App Service deployment.

Excludes the local venv, git, caches, local DB/logs. Strips pyodbc/pymssql from
requirements (Azure uses postgres via psycopg2; pyodbc needs unixODBC to build).
"""
import os
import zipfile

EXCLUDE_DIRS = {"venv", ".git", "__pycache__", "exports", "docs", ".vscode"}
EXCLUDE_EXT = {".db", ".log", ".sqlite3", ".ps1", ".zip"}
EXCLUDE_FILES = {".env", "app.zip", "build_deploy_zip.py"}

req_lines = open("requirements.txt").read().splitlines()
filtered = [l for l in req_lines
            if not l.strip().lower().startswith(("pyodbc", "pymssql", "#"))]

n = 0
with zipfile.ZipFile("app.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for dirpath, dirnames, filenames in os.walk("."):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if os.path.splitext(f)[1] in EXCLUDE_EXT or f in EXCLUDE_FILES:
                continue
            full = os.path.join(dirpath, f)
            arc = os.path.relpath(full, ".").replace(os.sep, "/")
            if arc == "requirements.txt":
                z.writestr("requirements.txt", "\n".join(filtered) + "\n")
            else:
                z.write(full, arc)
            n += 1

print("zipped files:", n)
print("deploy requirements:", filtered)
