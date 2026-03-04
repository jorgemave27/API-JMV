# Arquitectura - API JMV

## Capas

- **Routers**: endpoints HTTP (FastAPI)
- **Schemas**: validación/contratos (Pydantic)
- **Models**: tablas ORM (SQLAlchemy)
- **Database**: engine + sesión + dependency `get_db`
- **Core**: configuración y seguridad

## Flujo POST /items

Cliente -> Router (/items) -> Schema (ItemCreate valida) -> Model (Item) -> DB commit -> Response (ItemRead)
