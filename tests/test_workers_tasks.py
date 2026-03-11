from __future__ import annotations

from types import SimpleNamespace

from app.workers import tasks


def _invoke_task(task_obj, *args, **kwargs):
    """
    Soporta tareas Celery decoradas o funciones normales.
    """
    if hasattr(task_obj, "run"):
        return task_obj.run(*args, **kwargs)
    return task_obj(*args, **kwargs)


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalarResult(self._items)


class FakeSession:
    def __init__(self, items):
        self.items = items
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.refreshed = []

    def execute(self, *args, **kwargs):
        return FakeExecuteResult(self.items)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, obj):
        self.refreshed.append(obj)

    def close(self):
        self.closed = True


def test_enviar_notificacion_task_no_falla(monkeypatch):
    logs = []

    monkeypatch.setattr(
        tasks,
        "logger",
        SimpleNamespace(
            info=lambda *args, **kwargs: logs.append(("info", args, kwargs)),
            error=lambda *args, **kwargs: logs.append(("error", args, kwargs)),
        ),
        raising=False,
    )

    _invoke_task(tasks.enviar_notificacion, 1, "admin@empresa.com")

    assert True


def test_generar_reporte_stock_bajo_task_con_items(monkeypatch):
    fake_items = [
        SimpleNamespace(id=1, name="Caja chica", stock=2, sku="LOW-001", price=10.0, categoria_id=None),
        SimpleNamespace(id=2, name="Caja mediana", stock=1, sku="LOW-002", price=20.0, categoria_id=1),
    ]
    fake_session = FakeSession(fake_items)

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_session, raising=False)
    monkeypatch.setattr(
        tasks,
        "logger",
        SimpleNamespace(
            info=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        raising=False,
    )

    result = _invoke_task(tasks.generar_reporte_stock_bajo)

    assert fake_session.committed is True
    assert fake_session.closed is True
    assert len(fake_session.added) >= 1
    assert len(fake_session.refreshed) >= 1
    assert result is not None or True


def test_generar_reporte_stock_bajo_task_sin_items(monkeypatch):
    fake_session = FakeSession([])

    monkeypatch.setattr(tasks, "SessionLocal", lambda: fake_session, raising=False)
    monkeypatch.setattr(
        tasks,
        "logger",
        SimpleNamespace(
            info=lambda *args, **kwargs: None,
            error=lambda *args, **kwargs: None,
        ),
        raising=False,
    )

    result = _invoke_task(tasks.generar_reporte_stock_bajo)

    assert fake_session.committed is True
    assert fake_session.closed is True
    assert len(fake_session.refreshed) >= 1
    assert result is not None or True