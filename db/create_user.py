import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.auth import hash_password  # noqa: E402
from app.db import execute  # noqa: E402

ROLES = ("operator", "technician", "manager", "admin")

if len(sys.argv) < 3 or sys.argv[2] not in ROLES:
    raise SystemExit(f"Usage : python db/create_user.py <identifiant> <{'|'.join(ROLES)}> [\"Nom complet\"]")

username, role = sys.argv[1].strip().lower(), sys.argv[2]
full_name = sys.argv[3] if len(sys.argv) > 3 else ""
password = getpass.getpass("Mot de passe (8 caractères minimum) : ")
if len(password) < 8:
    raise SystemExit("Mot de passe trop court.")
if password != getpass.getpass("Confirmation : "):
    raise SystemExit("Les mots de passe diffèrent.")

execute("""INSERT INTO users(username, full_name, password_hash, role) VALUES (%s, %s, %s, %s)
           ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash,
               role = EXCLUDED.role, full_name = EXCLUDED.full_name, is_active = TRUE""",
        (username, full_name, hash_password(password), role))
print(f"Compte '{username}' ({role}) créé ou mis à jour.")