#!/usr/bin/env bash
# Cria os alertas do Cloud Monitoring para a VM do S5, que mandam e-mail quando:
#   - a CPU fica acima de 80 % por 5 min;
#   - a memória fica acima de 85 % por 5 min (precisa do Ops Agent);
#   - o disco passa de 80 % (precisa do Ops Agent).
# Os filtros pegam só VMs com o rótulo componente=s5, não as dos colegas.
#
# Uso:
#   GCP_PROJECT=<projeto> S5_ALERT_EMAIL=<seu-email> bash scripts/gcp/criar_alertas.sh
set -euo pipefail

: "${GCP_PROJECT:?Defina GCP_PROJECT}"
: "${S5_ALERT_EMAIL:?Defina S5_ALERT_EMAIL com o e-mail que recebe os alertas}"
gc() { gcloud --project "$GCP_PROJECT" "$@"; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

CHANNEL=$(gc beta monitoring channels list \
  --filter "type=\"email\" AND labels.email_address=\"$S5_ALERT_EMAIL\"" \
  --format 'value(name)' | head -1)
if [ -z "$CHANNEL" ]; then
  CHANNEL=$(gc beta monitoring channels create \
    --display-name "S5 - $S5_ALERT_EMAIL" --type email \
    --channel-labels "email_address=$S5_ALERT_EMAIL" --format 'value(name)')
fi
echo "Canal de notificação: $CHANNEL"

# As aspas vão escapadas porque os filtros entram dentro de strings do JSON.
VM_FILTER='resource.type = \"gce_instance\" AND metadata.user_labels.componente = \"s5\"'

# policy <nome> <filtro da métrica> <limite> <duração>
policy() {
  local name="$1" metric="$2" threshold="$3" duration="$4"
  if gc alpha monitoring policies list --filter "displayName=\"$name\"" \
       --format 'value(name)' | grep -q .; then
    echo "O alerta '$name' já existe."
    return
  fi
  cat > "$TMP/policy.json" <<EOF
{
  "displayName": "$name",
  "combiner": "OR",
  "conditions": [{
    "displayName": "$name",
    "conditionThreshold": {
      "filter": "$VM_FILTER AND $metric",
      "comparison": "COMPARISON_GT",
      "thresholdValue": $threshold,
      "duration": "$duration",
      "aggregations": [{"alignmentPeriod": "60s", "perSeriesAligner": "ALIGN_MEAN"}]
    }
  }],
  "notificationChannels": ["$CHANNEL"]
}
EOF
  gc alpha monitoring policies create --policy-from-file "$TMP/policy.json" >/dev/null
  echo "Alerta criado: $name"
}

policy "S5 - CPU acima de 80%" \
  'metric.type = \"compute.googleapis.com/instance/cpu/utilization\"' 0.8 300s
policy "S5 - memória acima de 85%" \
  'metric.type = \"agent.googleapis.com/memory/percent_used\" AND metric.labels.state = \"used\"' 85 300s
policy "S5 - disco acima de 80%" \
  'metric.type = \"agent.googleapis.com/disk/percent_used\" AND metric.labels.state = \"used\"' 80 60s
