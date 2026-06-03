# Auto-split from the original monolithic main.py. See git history.
import os
from dotenv import load_dotenv

load_dotenv()

f4d_admin_username = os.getenv("f4d_admin_username")
f4d_admin_password = os.getenv("f4d_admin_password")
super_admin_username = os.getenv("super_admin_username")
super_admin_password = os.getenv("super_admin_password")
