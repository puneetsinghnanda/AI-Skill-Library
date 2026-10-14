FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
# Unused Yarn apt source with a stale signing key breaks apt-get update; see the commit that added this file.
RUN rm -f /etc/apt/sources.list.d/yarn.list
