FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source used by the running FastAPI service.
COPY app ./app

# Include the automated tests and Pytest configuration in the image so a
# clean Docker build can run the test suite without relying on host mounts.
COPY tests ./tests
COPY pytest.ini ./pytest.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
