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


# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install Java (required for LanguageTool)
RUN apt-get update && \
    apt-get install -y openjdk-11-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 5000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]