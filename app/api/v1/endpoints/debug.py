from fastapi import APIRouter
import sentry_sdk

router = APIRouter()


@router.get("/error-test")
def error_test():
    try:
        raise Exception("🔥 Error de prueba Sentry")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        sentry_sdk.flush(timeout=5)
        raise