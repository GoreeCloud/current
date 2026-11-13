FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY LICENSE ./
COPY current ./current
RUN pip install --no-cache-dir .
RUN useradd --uid 10001 --create-home appuser
USER appuser
EXPOSE 8000
# Intentionally bind only to container loopback. Even `docker run -p`
# cannot make this listener reachable via its bridge interface by default.
# Any externally reachable bind is a separate, reviewed operator decision.
CMD ["uvicorn", "current.main:app", "--host", "127.0.0.1", "--port", "8000"]
