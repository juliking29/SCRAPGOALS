# --- Build Stage ---
FROM python:3.10-slim as builder

WORKDIR /app

# Instalar dependencias del sistema + Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instalar chromedriver (versión específica compatible)
RUN CHROME_MAJOR_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1) \
    && echo "Chrome major version: $CHROME_MAJOR_VERSION" \
    && wget -q https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1).0.0.0/linux64/chromedriver-linux64.zip -O chromedriver.zip \
    || wget -q https://chromedriver.storage.googleapis.com/$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1).0.0/chromedriver_linux64.zip -O chromedriver.zip \
    && unzip chromedriver.zip \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    || mv chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf chromedriver*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# --- Runtime Stage ---
FROM python:3.10-slim

WORKDIR /app

# Copiar desde el builder
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/chromedriver
COPY --from=builder /usr/bin/google-chrome /usr/bin/google-chrome
COPY --from=builder /usr/lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu

# Variables de entorno
ENV PATH="/root/.local/bin:${PATH}"
ENV PYTHONPATH="${PYTHONPATH}:/app"
ENV DISPLAY=:99
ENV CHROME_PATH=/usr/bin/google-chrome
ENV CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Dependencias mínimas para runtime
RUN apt-get update && apt-get install -y \
    libgl1 \
    libx11-6 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copiar el código
COPY . .

# Puerto y comando
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]