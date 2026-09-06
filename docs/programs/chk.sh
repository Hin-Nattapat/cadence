#!/usr/bin/env bash
# ไลบรารีสำหรับ verify-<program>.sh — source แล้วเรียก chk / ask / chk_summary
# เงียบเมื่อทุกอย่างผ่าน เพราะ hook เอา stdout ไปฉีดเข้า context

_CHK_FAILS=""
_CHK_ASKS=""
_CHK_FAIL_COUNT=0
_CHK_ASK_COUNT=0
_CHK_DIRTY=1

chk() { # chk <id> <label> <path> <anchor>
  local id="${1:-}" label="${2:-}" path="${3:-}" anchor="${4:-}"
  _CHK_DIRTY=1
  if [ "$#" -lt 4 ]; then
    _CHK_FAILS="${_CHK_FAILS}FAIL ${id:-?} bad usage — chk <id> <label> <path> <anchor>
"
    _CHK_FAIL_COUNT=$((_CHK_FAIL_COUNT + 1))
    return
  fi
  if [ -z "$anchor" ]; then
    _CHK_FAILS="${_CHK_FAILS}FAIL $id $label — empty anchor
"
    _CHK_FAIL_COUNT=$((_CHK_FAIL_COUNT + 1))
  elif [ ! -f "$path" ]; then
    _CHK_FAILS="${_CHK_FAILS}FAIL $id $label — ไม่พบไฟล์ $path
"
    _CHK_FAIL_COUNT=$((_CHK_FAIL_COUNT + 1))
  elif ! grep -qF -- "$anchor" "$path"; then
    _CHK_FAILS="${_CHK_FAILS}FAIL $id $label — ไม่พบ anchor '$anchor' ใน $path
"
    _CHK_FAIL_COUNT=$((_CHK_FAIL_COUNT + 1))
  fi
}

ask() { # ask <id> <question>  — premise 🔒 ที่มีแต่ผู้ใช้ตอบได้
  local id="${1:-}"
  _CHK_DIRTY=1
  if [ -z "$id" ]; then
    _CHK_FAILS="${_CHK_FAILS}FAIL ? bad usage — ask <id> <question>
"
    _CHK_FAIL_COUNT=$((_CHK_FAIL_COUNT + 1))
    return
  fi
  shift
  _CHK_ASKS="${_CHK_ASKS}ASK $id $*
"
  _CHK_ASK_COUNT=$((_CHK_ASK_COUNT + 1))
}

chk_summary() {
  [ -z "$_CHK_DIRTY" ] && return 0
  [ -n "$_CHK_FAILS" ] && printf '%s' "$_CHK_FAILS"
  [ -n "$_CHK_ASKS" ] && printf '%s' "$_CHK_ASKS"
  printf 'CHK-DONE %d/%d\n' "$_CHK_FAIL_COUNT" "$_CHK_ASK_COUNT"
  _CHK_FAILS=""
  _CHK_ASKS=""
  _CHK_FAIL_COUNT=0
  _CHK_ASK_COUNT=0
  _CHK_DIRTY=""
  return 0
}

trap chk_summary EXIT
