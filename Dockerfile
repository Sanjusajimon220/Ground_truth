FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY egms_tools ./egms_tools
RUN pip install --no-cache-dir -e ".[dev]"
COPY experiments ./experiments
COPY configs ./configs
ENTRYPOINT ["egms"]
CMD ["demo", "--out", "results"]
