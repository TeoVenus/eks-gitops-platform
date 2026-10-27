# Base image: slim Debian with Python, exact version matching local development
FROM python:3.14.9-slim

# Python settings for containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# All following commands run in /app (created automatically)
WORKDIR /app

# 1. Dependencies first (changes rarely -> cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Application code (changes often -> last)
COPY src ./src

# 3. Run as a non-root user
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# 4. Start the server (exec form, listen on all interfaces, no --reload)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
