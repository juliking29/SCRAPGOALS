FROM python:3.9-slim

# Instalar dependencias del sistema (todo en un solo RUN para reducir layers)
RUN apt-get update && \
    apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb && \
    rm -rf /var/lib/apt/lists/*

# Instalar Chrome (versión específica)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable=136.0.6949.63-1 && \
    rm -rf /var/lib/apt/lists/*

# Instalar ChromeDriver
RUN CHROMEDRIVER_VERSION=136.0.6949.63 && \
    wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" -O /tmp/chromedriver.zip && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/chromedriver && \
    rm /tmp/chromedriver.zip

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY . .

# Variables de entorno
ENV DISPLAY=:99
ENV PATH="/usr/local/bin:${PATH}"

# Comando para ejecutar
CMD Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 & \
    uvicorn main:app --host 0.0.0.0 --port 8000