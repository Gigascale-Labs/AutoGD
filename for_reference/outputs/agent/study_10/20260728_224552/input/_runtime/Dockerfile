FROM python:3.11-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git wget ca-certificates && rm -rf /var/lib/apt/lists/*

RUN command -v python3 || (apt-get update && apt-get install -y python3 python3-pip)
RUN pip install --no-cache-dir "numpy>=1.24,<3" 
RUN pip install --no-cache-dir "pandas>=1.5,<3" 
RUN pip install --no-cache-dir "scipy>=1.10,<2"
WORKDIR /workspace
RUN useradd -m runner && mkdir -p /app/data /app/artifacts /app/tmp && chown -R runner:runner /workspace /app
USER runner
CMD ["bash"]