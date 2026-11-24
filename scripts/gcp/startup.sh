#!/bin/bash
# Startup script da VM do S5. Roda a cada boot, então só instala o que falta:
# o Docker (com o plugin compose) e o Ops Agent, sem o qual a GCP não mostra memória nem disco.
# O contêiner volta sozinho depois de um boot por causa do restart: unless-stopped do compose.
set -e

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

if ! systemctl is-active --quiet google-cloud-ops-agent; then
  cd /tmp
  curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
  bash add-google-cloud-ops-agent-repo.sh --also-install
fi
