FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# WeasyPrint uses Pango and HarfBuzz to lay out text.  Installing only the
# runtime libraries keeps the image small while supporting the prebuilt Python
# wheels used by this project.  DejaVu provides predictable Latin/Greek fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source used by the running FastAPI service.
COPY app ./app

# Include the automated tests and Pytest configuration in the image so a
# clean Docker build can run the test suite without relying on host mounts.
COPY tests ./tests
COPY pytest.ini ./pytest.ini

# The local setup implementation is also inspected by an automated safety
# test.  Copy it into /app while keeping the repository-root setup.ps1 as the
# stable commands that users run from the repository root on Windows,
# Linux, or macOS.
COPY setup.ps1 ./setup.ps1
COPY setup.sh ./setup.sh

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
