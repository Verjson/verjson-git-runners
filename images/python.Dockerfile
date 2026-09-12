# Python runner: system Python 3 + pip/venv, plus the fast uv package manager.
# Build:  docker build -f images/python.Dockerfile -t gha-runner:python .
# Standalone builds use the public base; canonical publication overrides its exact digest.
ARG VERJSON_BASE_IMAGE=ghcr.io/verjson/gha-runner@sha256:3af0d4949ae7d1282be0cd7bcad0b8f0e5283dacaec014c536ca0ee2c808e7bb
FROM ${VERJSON_BASE_IMAGE}

COPY --chmod=0555 scripts/ensure-bubblewrap.sh /usr/local/bin/ensure-bubblewrap
USER root
RUN ["/usr/local/bin/ensure-bubblewrap"]
RUN rm -f /usr/local/bin/ensure-bubblewrap

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv python3-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

USER runner
ENV PATH=/home/runner/.local/bin:${PATH}
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
  && python3 --version && uv --version
COPY --chmod=0444 images/bubblewrap-provenance.json /etc/verjson-bubblewrap-provenance.json
COPY --chmod=0555 scripts/bubblewrap-image-contract.py /usr/local/bin/bubblewrap-image-contract
USER runner
RUN ["/usr/local/bin/bubblewrap-image-contract"]
