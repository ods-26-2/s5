"""Resume o CSV gravado por coletar_estatisticas.sh: mínimo, média, p95 e máximo de CPU,
memória e tamanho do banco, mais o período coberto. Só usa a biblioteca padrão, para rodar
direto na VM.

Uso:  python3 resumir_estatisticas.py s5-uso.csv
"""

import csv
import re
import statistics
import sys

_UNITS = {
    "b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9,
    "kib": 1024, "mib": 1024**2, "gib": 1024**3,
}


def _to_mib(text: str) -> float:
    match = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z]+)\s*", text)
    if not match:
        raise ValueError(f"tamanho inesperado: {text!r}")
    value, unit = match.groups()
    return float(value) * _UNITS[unit.lower()] / 1024**2


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def _line(name: str, unit: str, values: list[float]) -> str:
    return (
        f"{name:<14} mín {min(values):>9.2f}  média {statistics.mean(values):>9.2f}  "
        f"p95 {_p95(values):>9.2f}  máx {max(values):>9.2f}  {unit}"
    )


def main(path: str) -> None:
    with open(path, newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        sys.exit(f"{path} não tem amostras.")

    print(f"Amostras: {len(rows)}, de {rows[0]['timestamp']} a {rows[-1]['timestamp']}")
    print(f"Limite de memória do contêiner: {rows[-1]['mem_limite']}")
    print(_line("CPU", "% de 1 núcleo", [float(r["cpu_pct"]) for r in rows]))
    print(_line("Memória", "MiB", [_to_mib(r["mem_usado"]) for r in rows]))
    data = [float(r["dados_kb"]) / 1024 for r in rows if r["dados_kb"]]
    if data:
        print(_line("Banco (/data)", "MiB", data))
    print(f"Rede (entrada / saída) acumulada: {rows[-1]['rede_entrada_saida']}")
    print(f"Disco (leitura / escrita) acumulado: {rows[-1]['disco_leitura_escrita']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
