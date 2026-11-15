#!/bin/sh
# =============================================================================
# Резервна копія Prime Academy: база, файли кабінету, PDF сертифікатів.
#
#   cd /шлях/до/english_app_info && sh scripts/backup.sh
#
# Що робить:
#   1. pg_dump бази у форматі custom (-Fc): стиснутий, відновлюється pg_restore.
#   2. tar тому з файлами кабінету (/data/uploads у контейнері backend).
#   3. tar папки ./certificates (PDF виданих сертифікатів).
#   4. Видаляє копії, старші за KEEP_DAYS (за замовчуванням 14).
#   5. Якщо задано BACKUP_REMOTE і встановлено rclone — копіює все поза сервер.
#
# Паролів тут немає: pg_dump запускається всередині контейнера db, де
# POSTGRES_USER / POSTGRES_DB уже є в оточенні (з backend/.env).
#
# Працює з ПРОД-compose (docker-compose.yml). Запускати на сервері з кореня репо.
# Cron і відновлення — DEPLOY.md, розділ «Бекапи».
# =============================================================================
set -eu

BACKUP_DIR="${BACKUP_DIR:-/var/backups/prime}"
KEEP_DAYS="${KEEP_DAYS:-14}"
COMPOSE="${COMPOSE:-docker compose}"
STAMP="$(date +%Y-%m-%d_%H%M)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"          # у дампі персональні дані учнів
cd "$(dirname "$0")/.."

log() { echo "[$(date '+%F %T')] $*"; }

# Обірвалось посередині — недописаних .part не лишаємо.
trap 'rm -f "$BACKUP_DIR"/*.part' EXIT

# Пишемо в .part і перейменовуємо лише після успіху: обірваний дамп
# не повинен виглядати як справжня копія.
DB="$BACKUP_DIR/prime-db-$STAMP.dump"
log "база → $DB"
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DB.part"
[ -s "$DB.part" ] || { log "ПОМИЛКА: дамп порожній"; rm -f "$DB.part"; exit 1; }
mv "$DB.part" "$DB"

UP="$BACKUP_DIR/prime-uploads-$STAMP.tar.gz"
log "файли кабінету → $UP"
$COMPOSE exec -T backend tar -C /data -czf - uploads > "$UP.part"
mv "$UP.part" "$UP"

if [ -d certificates ]; then
  CERT="$BACKUP_DIR/prime-certificates-$STAMP.tar.gz"
  log "сертифікати → $CERT"
  tar -czf "$CERT.part" certificates
  mv "$CERT.part" "$CERT"
fi

log "видаляю копії, старші за $KEEP_DAYS днів"
find "$BACKUP_DIR" -maxdepth 1 -name 'prime-*' -type f -mtime +"$((KEEP_DAYS - 1))" -delete

if [ -n "${BACKUP_REMOTE:-}" ]; then
  if command -v rclone >/dev/null 2>&1; then
    log "копія поза сервер → $BACKUP_REMOTE"
    rclone copy "$BACKUP_DIR" "$BACKUP_REMOTE" --max-age 25h
  else
    log "УВАГА: BACKUP_REMOTE задано, але rclone не встановлено — копія лишилась лише на сервері"
  fi
fi

log "готово: $(du -sh "$BACKUP_DIR" | cut -f1) у $BACKUP_DIR"
