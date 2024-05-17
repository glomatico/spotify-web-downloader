# Dockerfile for building Spotify Web Downloader image

# Use the official Python image
FROM python:3.8-slim-buster

# Install ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Create a non-root user
ARG UID=1000
RUN useradd -m -u $UID user
USER user

WORKDIR /app

# Copy app files
COPY ./spotify_web_downloader ./spotify_web_downloader
COPY ./pyproject.toml .
COPY ./requirements.txt .

# Add the local user's bin directory to the PATH
ENV PATH="/home/user/.local/bin:${PATH}"

# Install the app
RUN pip install --user --no-cache-dir spotify-web-downloader
