#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
repo_dir=$PWD
state_dir=/workspace/.hackaton-runpod
backend_python=$state_dir/backend-venv/bin/python
whisper_python=$repo_dir/.venv-whisper/bin/python
model_dir=$repo_dir/models/whisper-large-v3-turbo
worker_pid=
api_pid=

if (( EUID != 0 )); then
    echo "Run this from the RunPod root terminal." >&2
    exit 1
fi

cleanup() {
    if [[ -n "$api_pid" ]]; then
        kill "$api_pid" 2>/dev/null || true
        wait "$api_pid" 2>/dev/null || true
    fi
    if [[ -n "$worker_pid" ]]; then
        kill "$worker_pid" 2>/dev/null || true
        wait "$worker_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

port_is_open() {
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

if port_is_open 8000; then
    echo "Port 8000 is already in use. Check /api/menus or stop the existing API before restarting." >&2
    exit 1
fi

if ! port_is_open 8765; then
    if [[ ! -x "$whisper_python" || ! -f "$model_dir/model.safetensors" ]]; then
        echo "Whisper setup is missing. Expected .venv-whisper and models/whisper-large-v3-turbo under $repo_dir." >&2
        exit 1
    fi
fi

packages=()
if [[ -z "${DATABASE_URL:-}" ]] && ! compgen -G '/usr/lib/postgresql/*/bin/pg_ctl' >/dev/null; then
    packages+=(postgresql)
fi
if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
    packages+=(ffmpeg)
fi
if (( ${#packages[@]} )); then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
fi

mkdir -p "$state_dir"
if [[ ! -x "$backend_python" ]]; then
    if ! python3 -m venv "$state_dir/backend-venv"; then
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
        /usr/bin/python3 -m venv "$state_dir/backend-venv"
    fi
fi
requirements_hash=$(sha256sum backend/requirements.txt)
if [[ ! -f "$state_dir/requirements.sha256" || "$requirements_hash" != "$(cat "$state_dir/requirements.sha256")" ]]; then
    "$backend_python" -m pip install -r backend/requirements.txt
    printf '%s\n' "$requirements_hash" > "$state_dir/requirements.sha256"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    db_dir=$state_dir/postgres
    db_port=55432
    if [[ -f "$db_dir/PG_VERSION" ]]; then
        pg_bin=/usr/lib/postgresql/$(<"$db_dir/PG_VERSION")/bin
    else
        pg_bin=$(compgen -G '/usr/lib/postgresql/*/bin/pg_ctl' | sort -V | tail -n 1)
        pg_bin=${pg_bin%/pg_ctl}
    fi
    if [[ ! -x "$pg_bin/pg_ctl" ]]; then
        echo "Install PostgreSQL $(<"$db_dir/PG_VERSION") to reopen the existing database in $db_dir." >&2
        exit 1
    fi
    install -d -m 700 -o postgres -g postgres "$db_dir"
    if [[ ! -f "$db_dir/PG_VERSION" ]]; then
        runuser -u postgres -- "$pg_bin/initdb" -D "$db_dir" --auth-local=peer --auth-host=scram-sha-256
    fi
    if ! runuser -u postgres -- "$pg_bin/pg_ctl" -D "$db_dir" status >/dev/null; then
        runuser -u postgres -- "$pg_bin/pg_ctl" -D "$db_dir" -l "$db_dir/server.log" \
            -o "-h '' -k '$db_dir' -p $db_port" -w start
    fi
    pg_admin=(runuser -u postgres -- "$pg_bin/psql" -h "$db_dir" -p "$db_port" -XAt -d postgres)
    if [[ "$("${pg_admin[@]}" -c "SELECT 1 FROM pg_roles WHERE rolname = 'root'")" != 1 ]]; then
        "${pg_admin[@]}" -v ON_ERROR_STOP=1 -c 'CREATE ROLE root LOGIN'
    fi
    if [[ "$("${pg_admin[@]}" -c "SELECT 1 FROM pg_database WHERE datname = 'kiosk'")" != 1 ]]; then
        "${pg_admin[@]}" -v ON_ERROR_STOP=1 -c 'CREATE DATABASE kiosk OWNER root'
    fi
    export DATABASE_URL="postgresql:///kiosk?host=$db_dir&port=$db_port"
fi

export PYTHONPATH="$repo_dir/backend${PYTHONPATH:+:$PYTHONPATH}"
export VOICE_TRANSCRIPTION_URL=http://127.0.0.1:8765/transcribe

"$backend_python" -m app.db.migrate
"$backend_python" -m app.db.seed

if ! port_is_open 8765; then
    "$whisper_python" -m app.services.voice.whisper_worker --model-dir "$model_dir" \
        --device cuda --host 127.0.0.1 --port 8765 &
    worker_pid=$!
else
    echo "Using the running Whisper worker on port 8765."
fi

api_options=()
if [[ -f backend/.env ]]; then
    api_options+=(--env-file backend/.env)
fi
"$backend_python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 "${api_options[@]}" &
api_pid=$!
wait "$api_pid"
