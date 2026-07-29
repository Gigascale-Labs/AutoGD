FROM python:3.11-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git wget ca-certificates && rm -rf /var/lib/apt/lists/*

RUN command -v python3 || (apt-get update && apt-get install -y python3 python3-pip)
RUN pip3 install --no-cache-dir matplotlib==3.9.2 numpy==2.1.1 pandas==2.2.3 scipy==1.14.1 statsmodels==0.14.4
WORKDIR /workspace
RUN useradd -m runner && mkdir -p /app/data /app/artifacts /app/tmp && chown -R runner:runner /workspace /app
USER runner
CMD ["bash"]