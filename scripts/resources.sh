#!/usr/bin/env bash
#
#  resources.sh
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The machine's resources, shared by every repository and every session on it (STANDARDS section 5, "Resources").
#  Builds, tests and gates take their share from here instead of each assuming the whole machine:
#
#      scripts/resources.sh jobs              how many compiles at once: SNICHOLLS_JOBS, else a quarter of the cores,
#                                             at most one per 16 GB of memory, at least 1 (on a CI runner, CI=true,
#                                             every core: the runner is the job's own)
#      scripts/resources.sh gate-memory       the memory cap of one gate container: SNICHOLLS_GATE_MEMORY, else 24g
#      scripts/resources.sh gate-slots        how many gates may run at once on this machine: SNICHOLLS_GATE_SLOTS,
#                                             else 1
#      scripts/resources.sh status            who holds the gate slots now
#
#  Sourced, it also gives a gate its slot, held for the life of the calling shell:
#
#      . third_party/tooling/scripts/resources.sh
#      snicholls_gate_acquire "<repository> <what>"   # waits, telling the user who holds the slot, until one is free
#      trap 'snicholls_gate_release' EXIT              # the caller releases it (chain it into an existing trap)
#
#  A waiting gate looks again every SNICHOLLS_GATE_POLL seconds (default 10). The slots are directories under
#  SNICHOLLS_LOCK_DIR (default /tmp/snicholls-gates, the same for every session of
#  the user); mkdir makes taking one atomic. A slot whose holder has exited (killed, crashed) is taken back by the
#  next gate that wants it, so a slot is never lost for good. The functions work under `set -euo pipefail` and in
#  bash 3.2 (macOS) as in bash 5.
#

# Whether $1 is a positive whole number.
snicholls__count() {
    case "$1" in
        ""|*[!0-9]*|0*) return 1 ;;
    esac
}

snicholls_jobs() {
    if [ -n "${SNICHOLLS_JOBS:-}" ]; then
        if snicholls__count "$SNICHOLLS_JOBS"; then echo "$SNICHOLLS_JOBS"; return 0; fi
        echo "resources: SNICHOLLS_JOBS=$SNICHOLLS_JOBS is not a positive number; using the default" >&2
    fi
    local cpus mem_gb jobs by_mem
    cpus="$(getconf _NPROCESSORS_ONLN 2>/dev/null)" || cpus=4
    snicholls__count "$cpus" || cpus=4
    if [ "${CI:-}" = true ]; then   # a CI runner is the job's own machine, shared with no one
        echo "$cpus"
        return 0
    fi
    mem_gb="$(sysctl -n hw.memsize 2>/dev/null)" || mem_gb=""
    if snicholls__count "$mem_gb"; then
        mem_gb=$((mem_gb / 1073741824))
    else
        mem_gb="$(awk '/^MemTotal:/ {print int($2 / 1048576)}' /proc/meminfo 2>/dev/null)" || mem_gb=""
        snicholls__count "$mem_gb" || mem_gb=16
    fi
    jobs=$((cpus / 4))
    by_mem=$((mem_gb / 16))
    if [ "$by_mem" -lt "$jobs" ]; then jobs="$by_mem"; fi
    if [ "$jobs" -lt 1 ]; then jobs=1; fi
    echo "$jobs"
}

snicholls_gate_memory() { echo "${SNICHOLLS_GATE_MEMORY:-24g}"; }
snicholls_gate_slots() {
    local slots="${SNICHOLLS_GATE_SLOTS:-1}"
    if ! snicholls__count "$slots"; then
        echo "resources: SNICHOLLS_GATE_SLOTS=$slots is not a positive number; using 1" >&2
        slots=1
    fi
    echo "$slots"
}
snicholls_lock_dir() { echo "${SNICHOLLS_LOCK_DIR:-/tmp/snicholls-gates}"; }

# Whether a path is older than a minute (find's -mmin is in BSD and GNU find alike).
snicholls__old() {
    [ -n "$(find "$1" -maxdepth 0 -mmin +1 2>/dev/null)" ]
}

# Whether the slot directory's holder is still running. A slot with no pid yet is being taken, unless it is old.
# ps -p, not kill -0: kill -0 fails for another user's process, which is still running.
snicholls__slot_alive() {
    local pid
    if ! pid="$(cat "$1/pid" 2>/dev/null)" || [ -z "$pid" ]; then
        if snicholls__old "$1"; then return 1; else return 0; fi
    fi
    snicholls__count "$pid" || return 1
    ps -p "$pid" >/dev/null 2>&1
}

# Removes a slot whose holder has exited. Only one process reclaims a slot at a time (the mkdir of <slot>.reclaim),
# and it looks again once it has that, so two waiters can never both reclaim it, or reclaim one just taken.
snicholls__reclaim() {
    local slot="$1"
    if [ -d "$slot.reclaim" ] && snicholls__old "$slot.reclaim"; then
        rmdir "$slot.reclaim" 2>/dev/null || true   # its reclaimer died in the moment it held it
    fi
    mkdir "$slot.reclaim" 2>/dev/null || return 0
    if [ -d "$slot" ] && ! snicholls__slot_alive "$slot"; then
        rm -rf "$slot" 2>/dev/null || true   # another user's stale slot is theirs to remove
    fi
    rmdir "$slot.reclaim" 2>/dev/null || true
}

snicholls_gate_status() {
    local dir slot
    dir="$(snicholls_lock_dir)"
    for slot in "$dir"/slot-*; do
        case "$slot" in *.reclaim) continue ;; esac
        [ -d "$slot" ] || continue
        if snicholls__slot_alive "$slot"; then
            echo "$(basename "$slot"): $(cat "$slot/what" 2>/dev/null) (pid $(cat "$slot/pid" 2>/dev/null), since $(cat "$slot/since" 2>/dev/null))"
        else
            echo "$(basename "$slot"): stale (its holder has exited)"
        fi
    done
    return 0
}

# snicholls_gate_acquire <what>: take a gate slot for this shell, waiting for one; the caller calls snicholls_gate_release.
snicholls_gate_acquire() {
    local what="${1:-a gate}" dir slots i slot told=0
    dir="$(snicholls_lock_dir)"
    slots="$(snicholls_gate_slots)"
    if ! mkdir -p "$dir" 2>/dev/null || [ ! -w "$dir" ]; then
        echo "resources: cannot write the gate slots' directory $dir (SNICHOLLS_LOCK_DIR)" >&2
        return 2
    fi
    chmod 1777 "$dir" 2>/dev/null || true   # every user's sessions share it; only the owner of a slot removes it
    while :; do
        i=1
        while [ "$i" -le "$slots" ]; do
            slot="$dir/slot-$i"
            i=$((i + 1))
            if [ -d "$slot" ] && ! snicholls__slot_alive "$slot"; then
                snicholls__reclaim "$slot"   # its holder exited without releasing it
            fi
            if mkdir "$slot" 2>/dev/null; then
                echo "$what" >"$slot/what"
                date -u +%Y-%m-%dT%H:%M:%SZ >"$slot/since"
                echo "$$" >"$slot/pid"   # last: a slot with a pid is complete
                SNICHOLLS_GATE_SLOT="$slot"
                return 0
            fi
        done
        if [ "$told" = 0 ]; then
            echo "resources: waiting for a gate slot ($slots on this machine); held by:" >&2
            snicholls_gate_status | sed 's/^/  /' >&2 || true
            told=1
        fi
        sleep "${SNICHOLLS_GATE_POLL:-10}"
    done
}

# snicholls_gate_release: give the slot back. Safe to call twice, or without a slot; only the holder releases.
snicholls_gate_release() {
    if [ -n "${SNICHOLLS_GATE_SLOT:-}" ] && [ "$(cat "$SNICHOLLS_GATE_SLOT/pid" 2>/dev/null)" = "$$" ]; then
        rm -rf "$SNICHOLLS_GATE_SLOT" || true
    fi
    SNICHOLLS_GATE_SLOT=""
    return 0
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    set -euo pipefail
    case "${1:-}" in
        jobs) snicholls_jobs ;;
        gate-memory) snicholls_gate_memory ;;
        gate-slots) snicholls_gate_slots ;;
        status) snicholls_gate_status ;;
        *) echo "usage: resources.sh jobs | gate-memory | gate-slots | status" >&2; exit 2 ;;
    esac
fi
