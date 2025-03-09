FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install system dependencies
RUN apt-get update \
  && apt-get -y install gcc postgresql \
  && apt-get clean

WORKDIR /app

# Copy the project into the image
ADD . /app

# Delete .sqlite3 files
RUN find /app -name "*.sqlite3" -delete

# Sync the project into a new environment, using the frozen lockfile
RUN uv sync --frozen

ENTRYPOINT [ "/app/entrypoint.sh" ]