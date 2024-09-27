# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 to allow external access to the Flask app
EXPOSE 5000

# Define environment variable to ensure Python outputs all logs (including print statements) immediately
ENV PYTHONUNBUFFERED=1

# Command to run the Flask app
CMD ["python", "app.py"]
