# Build the frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory
WORKDIR /app

# Install uv
RUN pip install uv

# Copy the project configuration files
COPY pyproject.toml .
COPY README.md .
# COPY uv.lock .  # Uncomment if uv.lock exists

# Copy the rest of the application
COPY src/ src/

# Copy the frontend build artifacts
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# Install dependencies
# --system installs into the system python, which is fine in a container
# --no-cache prevents caching to keep image small
RUN uv pip install --system --no-cache .

# Expose the port the app runs on
EXPOSE 8080

# Run the application
# Assumes the application is an ASGI app named 'app' in 'resilix.main'
CMD ["uvicorn", "resilix.main:app", "--host", "0.0.0.0", "--port", "8080"]
