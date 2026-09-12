# Go runner: official Go toolchain installed under /usr/local/go.
# Build:  docker build -f images/go.Dockerfile -t gha-runner:go .
# Standalone builds use the public base; canonical publication overrides its exact digest.
ARG VERJSON_BASE_IMAGE=ghcr.io/verjson/gha-runner@sha256:3af0d4949ae7d1282be0cd7bcad0b8f0e5283dacaec014c536ca0ee2c808e7bb
FROM ${VERJSON_BASE_IMAGE}

COPY --chmod=0555 scripts/ensure-bubblewrap.sh /usr/local/bin/ensure-bubblewrap
USER root
RUN ["/usr/local/bin/ensure-bubblewrap"]
RUN rm -f /usr/local/bin/ensure-bubblewrap

ARG GO_VERSION=1.23.4
# TARGETARCH is provided by BuildKit (amd64 / arm64) and matches Go's download naming.
ARG TARGETARCH
RUN curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${TARGETARCH}.tar.gz" \
      | tar -C /usr/local -xz \
    && /usr/local/go/bin/go version
ENV PATH=/usr/local/go/bin:/home/runner/go/bin:${PATH} \
    GOPATH=/home/runner/go

COPY --chmod=0444 images/bubblewrap-provenance.json /etc/verjson-bubblewrap-provenance.json
COPY --chmod=0555 scripts/bubblewrap-image-contract.py /usr/local/bin/bubblewrap-image-contract
USER runner
RUN ["/usr/local/bin/bubblewrap-image-contract"]
