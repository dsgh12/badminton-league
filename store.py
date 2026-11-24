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


class StoreError(Exception):
    """화면에 그대로 보여줘도 되는 원인 설명(토큰과 저장소 이름은 담지 않는다)."""


def _explain(status):
    if status == 401:
        return "토큰이 올바르지 않거나 만료되었습니다. Secrets의 GITHUB_TOKEN을 확인하세요."
    if status == 403:
        return "토큰에 저장소 접근 권한이 없습니다. 토큰의 Contents 권한이 Read and write인지 확인하세요."
    if status == 404:
        return "데이터 저장소를 찾지 못했습니다. GITHUB_DATA_REPO 이름과 토큰의 저장소 선택을 확인하세요."
    return f"GitHub 응답 오류입니다. (상태 코드 {status})"


def _conf():
    try:
        repo = st.secrets["GITHUB_DATA_REPO"]  # 예: "아이디/badminton-data"
        token = st.secrets["GITHUB_TOKEN"]
    except (KeyError, FileNotFoundError):
        raise StoreError("Secrets에 GITHUB_TOKEN 또는 GITHUB_DATA_REPO가 없습니다.")
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
    try:
        resp = requests.request(method, f"{API}{endpoint}", headers=headers, params=params, json=body, timeout=15)
    except requests.RequestException:
        raise StoreError("GitHub에 연결하지 못했습니다. 잠시 후 다시 시도하세요.")
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
        # 파일이 아직 없는 것인지, 저장소에 접근하지 못하는 것인지 구분한다.
        repo_status, _ = _gh("GET", f"/repos/{repo}")
        if repo_status != 200:
            raise StoreError(_explain(404 if repo_status == 404 else repo_status))
        return [], None
    if status != 200:
        raise StoreError(_explain(status))
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
        raise StoreError(_explain(status))
    raise StoreError("동시에 저장하는 사람이 많아 저장하지 못했습니다. 잠시 후 다시 시도하세요.")


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
