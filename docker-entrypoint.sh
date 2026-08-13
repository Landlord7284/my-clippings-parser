#!/bin/sh
# Ajusta o dono do historico e dropa privilegio antes de subir o app.
#
# Com bind mount quem manda e o dono do diretorio no host, entao um container
# nao-root so escreve la se o UID bater. PUID/PGID deixam o proprio container
# resolver isso, que e o padrao esperado em NAS.
set -e

HISTORY_DIR="${HISTORY_DIR:-/data}"

# Ja veio como nao-root (`docker run --user` ou `user:` no compose): nao da
# para trocar dono nem dropar privilegio. Segue direto -- quem definiu o
# usuario tambem cuidou das permissoes do volume.
if [ "$(id -u)" != "0" ]; then
    exec "$@"
fi

# PUID/PGID em branco: comportamento historico da imagem, roda como root.
if [ -z "${PUID}" ] && [ -z "${PGID}" ]; then
    mkdir -p "${HISTORY_DIR}"
    exec "$@"
fi

RUN_UID="${PUID:-1000}"
RUN_GID="${PGID:-1000}"

mkdir -p "${HISTORY_DIR}"
# Falha silenciosa e proposital: em volume somente-leitura ou com mapeamento de
# usuario o chown nao passa, mas o app ainda pode ter acesso de escrita.
chown -R "${RUN_UID}:${RUN_GID}" "${HISTORY_DIR}" 2>/dev/null || true

exec gosu "${RUN_UID}:${RUN_GID}" "$@"
