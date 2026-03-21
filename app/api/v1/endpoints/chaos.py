from fastapi import APIRouter, HTTPException
import time
import threading

router = APIRouter()

CHAOS_STATE = {
    "slow_db": False,
    "redis_down": False,
    "memory_pressure": False
}


def reset_chaos(tipo: str):
    time.sleep(60)
    CHAOS_STATE[tipo] = False


@router.post("/admin/chaos/{tipo}")
def trigger_chaos(tipo: str):
    """
    Chaos Monkey endpoint
    Solo development
    Auto reset 60s
    """

    if tipo not in CHAOS_STATE:
        raise HTTPException(status_code=400, detail="Tipo inválido")

    CHAOS_STATE[tipo] = True

    # auto reset
    threading.Thread(target=reset_chaos, args=(tipo,), daemon=True).start()

    return {"message": f"Chaos {tipo} activado por 60s"}