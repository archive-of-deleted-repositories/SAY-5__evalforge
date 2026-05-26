FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

FROM base AS build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM base AS runtime
COPY --from=build /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=build /usr/local/bin /usr/local/bin
COPY src ./src
EXPOSE 8000
CMD ["uvicorn", "evalforge.api:app", "--host", "0.0.0.0", "--port", "8000"]
