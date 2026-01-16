# 1. Use Python 3.12 (Required for Django 6.0+)
FROM python:3.12-slim

# 2. Install System Dependencies (REQUIRED for pycairo & xhtml2pdf)
# We install:
# - build-essential: To compile C code
# - libcairo2-dev: The graphics engine for PDF generation
# - python3-dev & libffi-dev: For system-level Python tools
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libcairo2-dev \
    python3-dev \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Setup App Directory
ENV APP_HOME /app
WORKDIR $APP_HOME

# 4. Copy Files
COPY . ./

# 5. Install Python Libraries
# (This will now succeed because we installed libcairo2-dev above!)
RUN pip install --no-cache-dir -r requirements.txt

# 6. Start the Server
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 config.wsgi:application