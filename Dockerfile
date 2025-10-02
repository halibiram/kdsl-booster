# Use the recommended Ubuntu LTS version as a base
FROM ubuntu:20.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install SDK prerequisites and Python pip
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    attr \
    bc \
    build-essential \
    curl \
    file \
    gawk \
    git \
    gperf \
    jq \
    libhtml-parser-perl \
    libjson-perl \
    libncurses-dev \
    libssl-dev \
    libxml-libxml-perl \
    lzip \
    python3 \
    python3-pip \
    subversion \
    unzip \
    zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the SDK and MIPS requirements into the container
COPY keenetic-sdk-4.03 /opt/keenetic-sdk
COPY requirements-mips.txt /opt/

# Unpack the firmware to set up the toolchain
WORKDIR /opt/keenetic-sdk
RUN ./unpack.sh frimware.bin

# Set up environment for the MIPS toolchain
ENV PATH="/opt/keenetic-sdk/toolchain/bin:${PATH}"
ENV STAGING_DIR="/opt/keenetic-sdk/staging_dir/toolchain-mipsel_24kc_gcc-8.4.0_glibc-2.27"
ENV CC="mipsel-openwrt-linux-gcc"
ENV CXX="mipsel-openwrt-linux-g++"
ENV AR="mipsel-openwrt-linux-ar"
ENV AS="mipsel-openwrt-linux-as"
ENV LD="mipsel-openwrt-linux-ld"
ENV RANLIB="mipsel-openwrt-linux-ranlib"
ENV NM="mipsel-openwrt-linux-nm"
ENV STRIP="mipsel-openwrt-linux-strip"
ENV CFLAGS="-I${STAGING_DIR}/usr/include -I${STAGING_DIR}/include"
ENV LDFLAGS="-L${STAGING_DIR}/usr/lib -L${STAGING_DIR}/lib"

# Set working directory
WORKDIR /opt

# Build the MIPS wheels
RUN pip3 wheel --wheel-dir=/opt/wheelhouse -r requirements-mips.txt

# The container is now ready. To get the wheels, you can run:
# docker build -t mips-builder .
# docker run --rm -v $(pwd)/wheelhouse:/opt/wheelhouse mips-builder
# The wheels will be in the 'wheelhouse' directory on your host.