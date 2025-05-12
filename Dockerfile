# Use an official Python base image (choose a version compatible with your project)
FROM python:3.10-slim-buster

# Set the working directory
WORKDIR /app

# Install system dependencies:
# - wget and gnupg for adding Google's repo
# - google-chrome-stable (the browser)
# - chromedriver
# - Clean up apt lists afterwards to keep image size down
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    # Add Google Chrome repository
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    # Install Chrome and ChromeDriver
    && apt-get update \
    && apt-get install -y google-chrome-stable chromedriver \
    # Clean up
    && apt-get purge -y --auto-remove wget gnupg \
    && rm -rf /var/lib/apt/lists/* \
    # Optional: Create a link for chromedriver if needed, though package install usually puts it in PATH
    # && ln -s /usr/bin/chromedriver /usr/local/bin/chromedriver

# Copy requirements file
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port FastAPI runs on (default is 8000 for uvicorn)
EXPOSE 8000

# Command to run your application (adjust if needed)
# Use 0.0.0.0 to bind to all network interfaces within the container
CMD ["uvicorn", "your_main_script_name:app", "--host", "0.0.0.0", "--port", "8000"]