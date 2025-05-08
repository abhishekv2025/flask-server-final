# Use the official Python image for version 3.10.12 from the Docker Hub
FROM python:3.10.12-slim

# Set the working directory in the container
WORKDIR /app

# Install Java and other system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jre curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install LanguageTool dependencies (if needed)
RUN curl -L https://github.com/languagetool-org/languagetool/releases/download/5.8/languagetool-5.8.zip -o languagetool.zip && \
    unzip languagetool.zip && \
    rm languagetool.zip

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Specify the command to run the app
CMD ["python", "app.py"]
