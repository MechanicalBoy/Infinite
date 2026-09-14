FROM ubuntu:24.04

COPY tools/linux/deps-apt.sh /tmp/deps-apt.sh
RUN bash /tmp/deps-apt.sh && rm /tmp/deps-apt.sh

WORKDIR /src
ENV CCACHE_DIR=/root/.ccache
