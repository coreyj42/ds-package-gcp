# Use a lightweight Python base image
FROM python:3.11-slim

# Set environment variables
ENV POETRY_VERSION=2.0.1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1

# Install system dependencies required for Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        apt-transport-https \
        ca-certificates \
        gnupg \
        libssl-dev \
        libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install gcloud
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && apt-get update -y && apt-get install google-cloud-cli -y
    
# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry and gcloud to PATH
ENV PATH="/root/.local/bin:$PATH:/google-cloud-sdk/bin"

# Authorize access to artifact registry
RUN --mount=type=secret,id=gcp_token \
    poetry config http-basic.ds-packages oauth2accesstoken $(cat /run/secrets/gcp_token)
    
# Set the working directory in the container
WORKDIR /app

# Copy the whole codebase so the config can be called from the components
COPY . /app/

# Install the dependencies
RUN poetry self add keyring keyrings.google-artifactregistry-auth \
    && poetry install
