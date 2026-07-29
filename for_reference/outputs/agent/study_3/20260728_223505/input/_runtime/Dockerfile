FROM python:3.13-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git wget ca-certificates && rm -rf /var/lib/apt/lists/*

RUN command -v python3 || (apt-get update && apt-get install -y python3 python3-pip)
RUN pip3 install --no-cache-dir --upgrade pip && pip3 install --no-cache-dir setuptools==58.0.0 && pip3 install --no-cache-dir matplotlib==3.10.0 numpy==2.2.1 pandas==2.2.3 statsmodels==0.13.2
WORKDIR /workspace
RUN useradd -m runner && mkdir -p /app/data /app/artifacts /app/tmp && chown -R runner:runner /workspace /app
USER runner
CMD ["bash"]