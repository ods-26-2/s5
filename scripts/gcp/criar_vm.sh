#!/usr/bin/env bash
# Cria a VM do S5 no projeto da GCP compartilhado pela turma: VM com Docker e Ops Agent,
# regra de firewall só para a API e agenda que liga e desliga a VM sozinha.
# Tudo leva o rótulo componente=s5 e o nome do dono, para não se misturar com os recursos
# dos colegas. Se algo já existir, o script pula essa parte.
#
# Uso, na raiz do repositório:
#   GCP_PROJECT=<projeto> S5_ALLOWED_CIDR=<seu-ip>/32 bash scripts/gcp/criar_vm.sh
#
# Variáveis opcionais (padrão entre parênteses):
#   GCP_ZONE (us-central1-a)    S5_MACHINE_TYPE (e2-small)   S5_DISK_GB (20)
#   S5_VM_NAME (s5-metrics)     S5_OWNER (rafael)
#   S5_START_CRON ("0 8 * * 1-5")  S5_STOP_CRON ("0 22 * * *"), no fuso America/Sao_Paulo
set -euo pipefail

: "${GCP_PROJECT:?Defina GCP_PROJECT com o id do projeto da turma}"
: "${S5_ALLOWED_CIDR:?Defina S5_ALLOWED_CIDR com quem pode acessar a porta 8000, ex. 200.1.2.3/32}"
ZONE="${GCP_ZONE:-us-central1-a}"
REGION="${ZONE%-*}"
VM="${S5_VM_NAME:-s5-metrics}"
MACHINE="${S5_MACHINE_TYPE:-e2-small}"
DISK_GB="${S5_DISK_GB:-20}"
OWNER="${S5_OWNER:-rafael}"
START_CRON="${S5_START_CRON:-0 8 * * 1-5}"
STOP_CRON="${S5_STOP_CRON:-0 22 * * *}"
SCHEDULE="${VM}-horario"
FIREWALL="${VM}-api"

cd "$(dirname "$0")/../.."
gc() { gcloud --project "$GCP_PROJECT" "$@"; }

echo "Projeto $GCP_PROJECT, zona $ZONE, VM $VM ($MACHINE, ${DISK_GB} GB)"

if gc compute instances describe "$VM" --zone "$ZONE" >/dev/null 2>&1; then
  echo "A VM $VM já existe."
else
  echo "Criando a VM…"
  gc compute instances create "$VM" \
    --zone "$ZONE" \
    --machine-type "$MACHINE" \
    --image-family debian-12 --image-project debian-cloud \
    --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced \
    --tags "$VM" \
    --labels "componente=s5,dono=$OWNER" \
    --metadata-from-file startup-script=scripts/gcp/startup.sh
fi

if gc compute firewall-rules describe "$FIREWALL" >/dev/null 2>&1; then
  echo "A regra de firewall $FIREWALL já existe."
else
  echo "Liberando a porta 8000 só para $S5_ALLOWED_CIDR…"
  gc compute firewall-rules create "$FIREWALL" \
    --network default --direction INGRESS \
    --allow tcp:8000 --source-ranges "$S5_ALLOWED_CIDR" \
    --target-tags "$VM"
fi

if gc compute resource-policies describe "$SCHEDULE" --region "$REGION" >/dev/null 2>&1; then
  echo "A agenda $SCHEDULE já existe."
else
  echo "Criando a agenda: liga em '$START_CRON', desliga em '$STOP_CRON'…"
  gc compute resource-policies create instance-schedule "$SCHEDULE" \
    --region "$REGION" \
    --vm-start-schedule "$START_CRON" \
    --vm-stop-schedule "$STOP_CRON" \
    --timezone America/Sao_Paulo
fi
gc compute instances add-resource-policies "$VM" --zone "$ZONE" \
  --resource-policies "$SCHEDULE" 2>/dev/null || echo "A agenda já está ligada à VM."

echo
echo "Pronto. O startup script instala o Docker e o Ops Agent no primeiro boot (uns 2 min)."
echo "Entrar na VM:  gcloud --project $GCP_PROJECT compute ssh $VM --zone $ZONE"
echo "Desligar já:   gcloud --project $GCP_PROJECT compute instances stop $VM --zone $ZONE"
