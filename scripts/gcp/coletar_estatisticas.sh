#!/usr/bin/env bash
# Grava o uso do contêiner do S5 em CSV, uma linha a cada INTERVALO segundos: CPU, memória,
# rede, leitura e escrita em disco e o tamanho da pasta /data (o banco DuckDB).
# Enquanto o contêiner está parado, nenhuma linha é gravada.
#
# Uso, na VM (continua rodando depois de sair do SSH):
#   nohup bash coletar_estatisticas.sh ~/s5-uso.csv 60 >/dev/null 2>&1 &
# Para ver o resumo:  python3 resumir_estatisticas.py ~/s5-uso.csv
set -euo pipefail

OUT="${1:-s5-uso.csv}"
INTERVAL="${2:-60}"
CONTAINER="${S5_CONTAINER:-s5-metrics}"

[ -s "$OUT" ] || echo "timestamp,cpu_pct,mem_usado,mem_limite,mem_pct,rede_entrada_saida,disco_leitura_escrita,dados_kb" > "$OUT"

while true; do
  stats=$(docker stats --no-stream \
    --format '{{.CPUPerc}};{{.MemUsage}};{{.MemPerc}};{{.NetIO}};{{.BlockIO}}' \
    "$CONTAINER" 2>/dev/null || true)
  if [ -n "$stats" ]; then
    IFS=';' read -r cpu mem mem_pct net block <<<"$stats"
    data_kb=$(docker exec "$CONTAINER" du -sk /data 2>/dev/null | cut -f1 || true)
    echo "$(date -Iseconds),${cpu%\%},${mem%% / *},${mem##* / },${mem_pct%\%},\"$net\",\"$block\",$data_kb" >> "$OUT"
  fi
  sleep "$INTERVAL"
done
