# Use official Playwright image that already includes browser binaries + deps
FROM mcr.microsoft.com/playwright/python:latest

# Create app dir
WORKDIR /app

# Copy script
COPY fetch.py /app/fetch.py

# Install the Playwright Python package (and any other dependencies)
RUN pip install --no-cache-dir --upgrade pip playwright

# Optional: install browsers explicitly (redundant on noble, but safe)
RUN playwright install

# Make fetch.py executable and set entrypoint
ENTRYPOINT ["python", "/app/fetch.py"]
