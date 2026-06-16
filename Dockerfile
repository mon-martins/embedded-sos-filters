# Test environment: Python + scientific stack + a C compiler.
#
# Gives the same toolchain locally and in CI, so the compile and golden tests
# build the C library with a 64-bit gcc and load it via ctypes without the
# host needing any compiler setup.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir numpy scipy matplotlib pytest

WORKDIR /work
CMD ["pytest", "-v"]
