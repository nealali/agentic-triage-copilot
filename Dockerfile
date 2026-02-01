FROM python:3.11-slim

# Basic container settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (better Docker layer caching)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r /app/requirements.txt

# Copy application code
COPY apps /app/apps
COPY agent /app/agent
COPY eval /app/eval
COPY pyproject.toml /app/pyproject.toml

EXPOSE 8000

# Run the API
CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

