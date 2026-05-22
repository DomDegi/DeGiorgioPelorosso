FROM python:3.10-slim

# Avoid creating .pyc files and ensure logs are printed to the terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Setup a working directory inside the container
WORKDIR /workspace

# Updates system and installs git
RUN apt-get update && apt-get install -y git

# Copy ONLY the requirements file at the beginning (leverage Docker cache)
COPY requirements*.txt .

# Update pip and install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements_dev.txt

# (Optional) Install additional tools for debugging that might not be in the txt
RUN pip install pytest

# Start a shell when the container runs
CMD ["bash"]

# Change this to whatever your main execution script is
# This is what Slurm will run by default
CMD ["python", "main.py"]
