# Use Python 3.13 slim base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by Chrome
RUN apt-get update -y && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libx11-6 \
    libx11-dev \
    libxss1 \
    libcups2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libnspr4 \
    libnss3 \
    libnss3-dev \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libdbus-1-3 \
    libxtst6 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libgbm1 \
    libegl1 \
    libasound2 \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome stable
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i google-chrome-stable_current_amd64.deb \
    && apt-get install -f -y \
    && rm google-chrome-stable_current_amd64.deb

# Install Chromedriver matching the installed Chrome version
RUN LATEST_CHROMEDRIVER=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE) \
    && wget https://chromedriver.storage.googleapis.com/${LATEST_CHROMEDRIVER}/chromedriver_linux64.zip \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver_linux64.zip

# Copy Python dependencies and install
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend code
COPY backend /app/backend

# Set Python path
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
