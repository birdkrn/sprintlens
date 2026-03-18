FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY sprintlens/ sprintlens/
COPY templates/ templates/
COPY static/ static/
COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]
