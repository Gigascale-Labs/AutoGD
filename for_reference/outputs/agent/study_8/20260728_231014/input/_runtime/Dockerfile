FROM python:3.11-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git wget ca-certificates && rm -rf /var/lib/apt/lists/*

RUN command -v python3 || (apt-get update && apt-get install -y python3 python3-pip)
RUN python3 -m pip install --no-cache-dir numpy 
RUN python3 -m pip install --no-cache-dir pandas 
RUN python3 -m pip install --no-cache-dir scipy 
RUN python3 -m pip install --no-cache-dir statsmodels
WORKDIR /workspace
RUN useradd -m runner && mkdir -p /app/data /app/artifacts /app/tmp && chown -R runner:runner /workspace /app
USER runner
CMD ["bash"]