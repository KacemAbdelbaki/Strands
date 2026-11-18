# Stage 1 runs on the build machine's own CPU and downloads wheels for the target CPU.
# Running pip under ARM emulation on a PC takes over 20 minutes and can stall the machine.
FROM --platform=$BUILDPLATFORM python:3.13-slim AS deps
ARG TARGETARCH
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md LICENSE constraints.txt ./
COPY src ./src
RUN pip wheel --no-deps --wheel-dir /wheels . \
    && case "$TARGETARCH" in arm64) arch=aarch64 ;; amd64) arch=x86_64 ;; *) exit 1 ;; esac \
    && pip install /wheels/*.whl \
        --constraint constraints.txt \
        --target /deps \
        --implementation cp --python-version 3.13 --only-binary=:all: \
        --platform "manylinux2014_$arch" \
        --platform "manylinux_2_17_$arch" \
        --platform "manylinux_2_26_$arch" \
        --platform "manylinux_2_27_$arch" \
        --platform "manylinux_2_28_$arch" \
        --platform "manylinux_2_31_$arch" \
        --platform "manylinux_2_34_$arch" \
        --platform "manylinux_2_35_$arch" \
        --platform "manylinux_2_36_$arch"

# Stage 2 is the image that runs. python:3.13-slim is Debian with glibc 2.36+, matching the tags above.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/deps \
    PATH=/deps/bin:$PATH

COPY --from=deps /deps /deps

# All state lives in /data, which Compose mounts from the host
ENV STRANDS_DATA_DIR=/data \
    HOME=/data \
    CLOUD_MODE=true

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown app:app /data
USER app
VOLUME /data

HEALTHCHECK --interval=1m --timeout=10s --start-period=1m \
    CMD ["python", "-m", "strands_assistant.healthcheck"]

CMD ["strands-assistant"]
