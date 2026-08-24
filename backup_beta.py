from pathlib import Path
from datetime import datetime
import shutil, zipfile

BASE = Path(__file__).parent
instance = BASE / "instance"
uploads = BASE / "static" / "uploads"
backup_dir = BASE / "backups"
backup_dir.mkdir(exist_ok=True)

stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
archive = backup_dir / f"odna-druga-beta-backup-{stamp}.zip"

with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for db in instance.glob("*.db"):
        z.write(db, f"instance/{db.name}")
    for f in uploads.glob("*"):
        if f.is_file():
            z.write(f, f"static/uploads/{f.name}")

print(f"Backup created: {archive}")
