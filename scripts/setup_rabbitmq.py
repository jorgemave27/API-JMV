import asyncio
import sys
from pathlib import Path

# -----------------------------------------------------
# Agregar root del proyecto al PYTHONPATH
# -----------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.messaging.setup import setup_messaging

asyncio.run(setup_messaging())
