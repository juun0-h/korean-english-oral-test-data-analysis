FROM apache/airflow:2.9.3-python3.9

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy requirements and readme
COPY pyproject.toml README.md

# Install uv
RUN pip install uv

# Install dependencies (to user site)
RUN uv pip install -e .

# Copy airflow configuration
COPY airflow/airflow.cfg /opt/airflow/airflow.cfg
COPY airflow/webserver_config.py /opt/airflow/webserver_config.py

# Set environment variables
ENV PYTHONPATH="/opt/airflow:${PYTHONPATH}"