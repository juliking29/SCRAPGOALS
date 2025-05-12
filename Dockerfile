# Usa una imagen base de Python slim con versión explícita
FROM python:3.10-slim as builder

# --- Etapa de construcción ---
# 1. Instalar dependencias del sistema y Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    unzip \
    # Dependencias para Chrome
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalar Google Chrome (versión estable)
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 3. Obtener versión exacta de Chrome instalado
RUN CHROME_VERSION=$(google-chrome-stable --version | awk '{print $3}') \
    && echo "Chrome version: $CHROME_VERSION"

# 4. Instalar Chromedriver compatible
RUN CHROME_MAJOR_VERSION=$(google-chrome-stable --version | awk '{print $3}' | cut -d '.' -f 1) \
    && CHROMEDRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR_VERSION) \
    && echo "Installing Chromedriver version: $CHROMEDRIVER_VERSION" \
    && wget -q https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip -O /tmp/chromedriver.zip \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && mv /tmp/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# 5. Instalar dependencias de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# --- Etapa de ejecución ---
FROM python:3.10-slim

# 1. Copiar solo lo necesario desde la etapa de construcción
COPY --from=builder /usr/bin/google-chrome-stable /usr/bin/google-chrome-stable
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/chromedriver
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/share/fonts /usr/share/fonts
COPY --from=builder /usr/lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu

# 2. Variables de entorno
ENV PATH="/root/.local/bin:$PATH"
ENV CHROME_PATH=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver
ENV DISPLAY=:99

# 3. Dependencias mínimas para runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# 4. Configurar el directorio de trabajo
WORKDIR /app
COPY . .

# 5. Puerto y comando de inicio
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]