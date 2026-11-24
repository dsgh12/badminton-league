"""저장소: GitHub 저장소의 JSON 파일에 경기 기록을 저장한다. 명단은 Streamlit secrets에서 읽는다.

- 기록 파일은 비공개 데이터 저장소에 두고, 앱은 토큰으로 읽고 쓴다.
- 여러 명이 동시에 쓰면 GitHub가 충돌(409)을 알려 주므로 최신 내용을 다시 읽고 재시도한다.
"""
import base64
import json
import random
import time
import uuid
from datetime import datetime, timezone

import requests
import streamlit as st

API = "https://api.github.com"
RETRIES = 6


def _conf():
    repo = st.secrets["GITHUB_DATA_REPO"]  # 예: "아이디/badminton-data"
    token = st.secrets["GITHUB_TOKEN"]
    branch = st.secrets.get("GITHUB_DATA_BRANCH", "main")
    path = st.secrets.get("GITHUB_DATA_PATH", "matches.json")
    return repo, token, branch, path


def _gh(method, endpoint, params=None, body=None):
    """GitHub API 호출. (상태코드, JSON)을 돌려준다."""
    _, token, _, _ = _conf()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.request(method, f"{API}{endpoint}", headers=headers, params=params, json=body, timeout=15)
    try:
        data = resp.json() if resp.content else None
    except ValueError:
        data = None
    return resp.status_code, data


def roster():
    """반 명단을 순서대로 돌려준다: [{'id': '21201', 'name': '...'}, ...]"""
    return [{"id": str(r["id"]).strip(), "name": str(r["name"]).strip()} for r in st.secrets["roster"]]


def _read():
    """(기록 목록, 파일 sha)를 돌려준다. 파일이 아직 없으면 ([], None)."""
    repo, _, branch, path = _conf()
    status, data = _gh("GET", f"/repos/{repo}/contents/{path}", params={"ref": branch})
    if status == 404:
        return [], None
    if status != 200:
        raise RuntimeError(f"GitHub 읽기 실패: {status}")
    text = base64.b64decode(data["content"]).decode("utf-8")
    rows = json.loads(text) if text.strip() else []
    return rows, data["sha"]


def _write(rows, sha, message):
    repo, _, branch, path = _conf()
    content = json.dumps(rows, ensure_ascii=False, indent=1)
    body = {"message": message, "content": base64.b64encode(content.encode("utf-8")).decode("ascii"), "branch": branch}
    if sha:
        body["sha"] = sha
    status, _data = _gh("PUT", f"/repos/{repo}/contents/{path}", body=body)
    return status


def _mutate(change, message):
    """최신 기록을 읽어 change(rows)를 적용하고 저장한다. 충돌하면 다시 읽어 재시도한다.

    change는 새 목록을 돌려주거나, 바꿀 게 없으면 None을 돌려준다. 저장되었으면 True.
    """
    for _attempt in range(RETRIES):
        rows, sha = _read()
        new_rows = change(rows)
        if new_rows is None:
            return False
        status = _write(new_rows, sha, message)
        if status in (200, 201):
            matches.clear()
            return True
        if status in (409, 422):  # 다른 사람이 먼저 저장함
            time.sleep(random.uniform(0.2, 0.8))
            continue
        raise RuntimeError(f"GitHub 쓰기 실패: {status}")
    raise RuntimeError("동시에 저장하는 사람이 많아 저장하지 못했습니다.")


@st.cache_data(ttl=10, show_spinner=False)
def matches():
    """모든 경기 기록을 등록 순서대로 돌려준다. 모든 접속자가 10초 동안 같은 결과를 공유한다."""
    rows, _ = _read()
    return rows


def add_match(row):
    new = dict(row, id=uuid.uuid4().hex, created_at=datetime.now(timezone.utc).isoformat())
    return _mutate(lambda rows: rows + [new], "경기 기록 추가")


def update_match(match_id, writer_id, row):
    """본인이 쓴 기록만 고친다. 고쳐졌으면 True."""
    def change(rows):
        if not any(r["id"] == match_id and r["writer_id"] == writer_id for r in rows):
            return None
        return [dict(r, **row) if (r["id"] == match_id and r["writer_id"] == writer_id) else r for r in rows]
    return _mutate(change, "경기 기록 수정")


def delete_match(match_id, writer_id):
    """본인이 쓴 기록만 지운다. 지워졌으면 True."""
    def change(rows):
        if not any(r["id"] == match_id and r["writer_id"] == writer_id for r in rows):
            return None
        return [r for r in rows if not (r["id"] == match_id and r["writer_id"] == writer_id)]
    return _mutate(change, "경기 기록 삭제")
