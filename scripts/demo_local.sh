#!/usr/bin/env bash
# Demonstração completa do S5 na máquina local, sem tocar em nenhum broker compartilhado:
# sobe um Kafka local e o S5 em Docker (com os artefatos de exemplo), publica mensagens de
# exemplo do S1 e do S2, mostra as métricas que o S5 publica e faz duas consultas.
# Ao terminar, ou com Ctrl+C, desliga os dois contêineres.
#
# Uso, na raiz do repositório, com o venv ativado:
#     source .venv/bin/activate
#     bash scripts/demo_local.sh
set -euo pipefail

cd "$(dirname "$0")/.."
BROKER="localhost:9092"
KAFKA_CONTAINER="s5-demo-kafka"
S5_CONTAINER="s5-demo"
IMAGE="ods/s5-metrics:demo"

cleanup() {
  docker stop "$S5_CONTAINER" "$KAFKA_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() { echo "ERRO: $*" >&2; exit 1; }

command -v docker >/dev/null || fail "Docker não encontrado."
python -c "import confluent_kafka" 2>/dev/null || fail "Ative o venv do S5: source .venv/bin/activate"
for port in 9092 8000; do
  if ss -ltn 2>/dev/null | grep -q ":$port "; then
    fail "A porta $port já está em uso. Pare o que estiver nela (um socat ou outro Kafka?) e rode de novo."
  fi
done

echo "Construindo a imagem do S5…"
docker build -q -t "$IMAGE" . >/dev/null

echo "Subindo o Kafka local…"
docker run -d --rm --name "$KAFKA_CONTAINER" -p 127.0.0.1:9092:9092 apache/kafka:3.9.0 >/dev/null
for _ in $(seq 60); do
  docker logs "$KAFKA_CONTAINER" 2>&1 | grep -q "Kafka Server started" && break
  sleep 1
done
docker logs "$KAFKA_CONTAINER" 2>&1 | grep -q "Kafka Server started" || fail "O Kafka local não subiu em 60 s."
python scripts/demo_publish.py topicos "$BROKER"

echo "Subindo o S5 com os artefatos de exemplo (zones-a8-2, cal-cam0-3)…"
docker run -d --rm --name "$S5_CONTAINER" --network host \
  -e S5_KAFKA_BROKERS="$BROKER" \
  -e S5_KAFKA_GROUP_ID="S5-demo" \
  -e S5_TICK_SECONDS=1 \
  -e S5_DATABASE_PATH=":memory:" \
  -e S5_ARTIFACTS=/artifacts/zones-a8-2.descriptor.json,/artifacts/cal-cam0-3.descriptor.json \
  -v "$PWD/tests/fixtures/artifacts:/artifacts:ro" \
  "$IMAGE" >/dev/null
for _ in $(seq 30); do
  docker logs "$S5_CONTAINER" 2>&1 | grep -q "Application startup complete" && break
  sleep 1
done
docker logs "$S5_CONTAINER" 2>&1 | grep -q "Application startup complete" || fail "O S5 não subiu em 30 s."
docker logs "$S5_CONTAINER" 2>&1 | grep "Artefatos carregados" | sed 's/^.*s5: /   /'
# O S5 começa em `latest`: espera ele entrar no grupo antes de publicar.
sleep 10

python scripts/demo_publish.py executar "$BROKER"
