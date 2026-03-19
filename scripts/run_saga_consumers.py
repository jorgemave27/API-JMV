import asyncio
import sys
from pathlib import Path

# -----------------------------------------------------
# Agregar root del proyecto al PYTHONPATH
# -----------------------------------------------------
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.saga.consumers import run_saga_consumers

asyncio.run(run_saga_consumers())