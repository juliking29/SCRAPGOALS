# Usa una imagen base de Python slim
FROM python:3.9-slim

# Argumento para la versión de Chromedriver (más fácil de actualizar)
ARG CHROMEDRIVER_VERSION=136.0.7103.92

# 1. Instalar dependencias esenciales y herramientas de descarga
#    - Se usa gpg para manejar claves (apt-key está obsoleto)
#    - Se limpian las listas de apt y la caché al final
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    unzip \
    # Dependencias necesarias para Chrome Headless
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    fonts-liberation \
    libu2f-udev \
    xdg-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalar Google Chrome Stable
#    - Descarga la clave GPG y la guarda en el directorio recomendado
#    - Añade el repositorio de Chrome
#    - Instala Chrome estable
#    - Limpia la caché de apt
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Instalar Chromedriver compatible con la versión de Chrome instalada
#    - Usa la URL oficial de 'Chrome for Testing'
#    - Descarga el zip de Chromedriver para linux64
#    - Descomprime directamente en /usr/local/bin (simplificado)
#    - Elimina el archivo zip descargado
RUN CHROMEDRIVER_URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
    && echo "Descargando Chromedriver desde: ${CHROMEDRIVER_URL}" \
    && wget -q --show-progress -O /tmp/chromedriver.zip "${CHROMEDRIVER_URL}" \
    && unzip -o /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip \
    && rm -rf /tmp/chromedriver-linux64

# 4. Configuración del entorno (Opcional, pero buena práctica)
#    Selenium usualmente encuentra Chrome y Chromedriver si están en el PATH
ENV CHROME_PATH=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# 5. Preparar el directorio de la aplicación e instalar dependencias
WORKDIR /app
COPY requirements.txt .
# Instala dependencias de Python sin caché
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de la aplicación
COPY . .

# 6. Comando para ejecutar la aplicación (Asegúrate que coincida con tu app)
#    Ejemplo para FastAPI con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Verificación (Opcional, para debug local) ---
# docker build -t selenium-app . && docker run -it --rm selenium-app bash -c "google-chrome-stable --version && chromedriver --version"
