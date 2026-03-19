# Ruta: auth-service/Dockerfile

FROM python:3.11-slim

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero requirements para aprovechar caché
COPY requirements.txt .

# Instalamos dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el contenido del auth-service al contenedor
COPY . .

# Exponemos el puerto del servicio
EXPOSE 8001

# Comando de arranque
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
