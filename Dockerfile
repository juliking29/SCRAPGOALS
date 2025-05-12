# --- Build Stage ---
FROM python:3.10-slim as builder

WORKDIR /app

# Instalar dependencias del sistema (incluyendo Chrome para Selenium)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalar chromedriver compatible con la versión de Chrome
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1) \
    && CHROMEDRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}) \
    && wget -q https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && chmod +x chromedriver \
    && mv chromedriver /usr/local/bin/ \
    && rm chromedriver_linux64.zip

# Copiar requirements e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# --- Runtime Stage ---
FROM python:3.10-slim

WORKDIR /app

# Copiar desde el builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/chromedriver
COPY --from=builder /usr/bin/google-chrome /usr/bin/google-chrome

# Variables de entorno para Selenium
ENV PATH="/root/.local/bin:${PATH}"
ENV PYTHONPATH="${PYTHONPATH}:/app"
ENV DISPLAY=:99

# Dependencias mínimas del sistema para runtime
RUN apt-get update && apt-get install -y \
    libgl1 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# Copiar el código de la aplicación
COPY . .

# Puerto expuesto (para FastAPI)
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]