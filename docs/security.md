# Seguridad - Protección contra inyección SQL

## Qué se aprendió

La inyección SQL ocurre cuando el input del usuario se concatena directamente en una consulta SQL.

## Ejemplo inseguro

```python
sql = f"SELECT * FROM items WHERE name = '{nombre}'"
```
