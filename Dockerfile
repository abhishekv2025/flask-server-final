# # Use the official Python image for version 3.10.12 from the Docker Hub
# FROM python:3.10.12-slim

# # Set the working directory in the container
# WORKDIR /app

# # Install Java and other system dependencies
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends default-jre && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# # Copy the requirements file into the container
# COPY requirements.txt .

# # Install the Python dependencies
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the rest of the application code into the container
# COPY . .

# # Specify the command to run the app
# CMD ["python", "app.py"]

# # Expose the port the app runs on
# EXPOSE 5000

# Use an official Python runtime with a more compatible base
FROM python:3.9-slim-bookworm

# Install system dependencies first
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \  # Updated to Java 17 (more stable in Debian bookworm)
    ca-certificates \          # Helps with SSL certificates
    && rm -rf /var/lib/apt/lists/*

    
# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Set the working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 5000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]