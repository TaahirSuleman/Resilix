# Build the frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
ARG VITE_APP_VERSION=dev
ARG VITE_BUILD_SHA=local
ARG VITE_BUILD_TIME=unknown
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_BUILD_SHA=$VITE_BUILD_SHA
ENV VITE_BUILD_TIME=$VITE_BUILD_TIME
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Use an official Python runtime as a parent image
FROM python:3.12-slim
ARG APP_VERSION=dev
ARG BUILD_SHA=local
ARG BUILD_TIME=unknown

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV APP_VERSION=$APP_VERSION
ENV BUILD_SHA=$BUILD_SHA
ENV BUILD_TIME=$BUILD_TIME

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
