# Usa una imagen base oficial de Python (elige una versión compatible)
# ASEGÚRATE DE QUE ESTA LÍNEA (la siguiente) SEA EXACTAMENTE ASÍ:
FROM python:3.10-slim-buster

# Establece el directorio de trabajo
WORKDIR /app

# Instala dependencias del sistema:
# - ca-certificates: Necesario para conexiones HTTPS (wget)
# - wget y gnupg: Para añadir el repositorio de Google
# - google-chrome-stable: El navegador
# - chromedriver: El controlador para Selenium
# - Limpia las listas de apt al final para reducir el tamaño de la imagen
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    gnupg \
    # Añade la llave del repositorio de Google Chrome
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    # Añade la fuente del repositorio de Google Chrome
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list' \
    # Actualiza la lista de paquetes de nuevo DESPUÉS de añadir el nuevo repo
    && apt-get update \
    # Instala Chrome y ChromeDriver
    && apt-get install -y google-chrome-stable chromedriver \
    # Limpia los paquetes descargados y las listas
    && apt-get purge -y --auto-remove wget gnupg \
    && rm -rf /var/lib/apt/lists/*
    # ¡IMPORTANTE: NO hay barra invertida (\) al final de la línea anterior!

# Copia el archivo de requerimientos
COPY requirements.txt requirements.txt

# Instala las dependencias de Python
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu aplicación
COPY . .

# Expone el puerto en el que corre FastAPI (Usa 8000 o $PORT si Railway lo asigna)
EXPOSE 8000

# Comando para ejecutar tu aplicación (ajusta si es necesario)
# Reemplaza 'your_main_script_name:app' con el nombre correcto
CMD ["uvicorn", "your_main_script_name:app", "--host", "0.0.0.0", "--port", "8000"]