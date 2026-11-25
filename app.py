import hmac
import html
import unicodedata
from datetime import date, datetime
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import store

KST = ZoneInfo("Asia/Seoul")

st.set_page_config(page_title="우리 반 배드민턴 리그", layout="centered")

CSS = """
<style>
.bn { background-color:#1b6b4f;
  background-image: linear-gradient(rgba(255,255,255,.28),rgba(255,255,255,.28)),
                    linear-gradient(rgba(255,255,255,.28),rgba(255,255,255,.28)),
                    linear-gradient(90deg,rgba(255,255,255,.28),rgba(255,255,255,.28));
  background-size:100% 2px,100% 2px,2px 100%;
  background-position:0 14px,0 calc(100% - 14px),50% 0;
  background-repeat:no-repeat; color:#fff; padding:26px 20px; border-radius:12px; margin-bottom:10px; }
.bn .t { font-size:1.7rem; font-weight:800; line-height:1.2; }
.pod { display:grid; grid-template-columns:1fr 1.15fr 1fr; gap:8px; align-items:end; margin:6px 0 20px; }
.slot { display:flex; flex-direction:column; align-items:center; text-align:center; min-width:0; }
.slot .nm { font-weight:700; font-size:1.05rem; overflow-wrap:anywhere; }
.slot .sub { font-size:.8rem; opacity:.7; }
.slot.me .nm { color:#1b8f66; }
.slot.empty { opacity:.4; }
.medal { width:44px; height:44px; border-radius:50%; display:grid; place-items:center; font-weight:800; font-size:1.2rem; color:#fff; margin-bottom:6px; }
.p1 .medal { background:#d9a400; width:54px; height:54px; font-size:1.5rem; }
.p2 .medal { background:#8a97a0; }
.p3 .medal { background:#b5703a; }
.blk { width:100%; margin-top:8px; border-radius:10px 10px 0 0; border:1px solid rgba(128,128,128,.3); border-bottom:0;
  background:rgba(128,128,128,.10); display:grid; place-items:center; font-weight:800; font-size:1.6rem; opacity:.85; }
.p1 .blk { height:96px; border-top:5px solid #d9a400; }
.p2 .blk { height:70px; border-top:5px solid #8a97a0; }
.p3 .blk { height:52px; border-top:5px solid #b5703a; }
.rt { border:1px solid rgba(128,128,128,.3); border-radius:12px; overflow:hidden; }
.rt .r { display:grid; grid-template-columns:40px minmax(0,1fr) 38px 38px 38px 54px 50px; gap:4px; align-items:center;
  padding:10px 12px; border-bottom:1px solid rgba(128,128,128,.2); font-variant-numeric:tabular-nums; min-height:46px; }
.rt .r:last-child { border-bottom:0; }
.rt .h { font-size:.75rem; opacity:.65; background:rgba(128,128,128,.10); }
.rt .r.me { background:rgba(27,143,102,.16); }
.rt .rk { font-weight:800; font-size:1.05rem; }
.rt .n { text-align:right; }
.pos { color:#1b8f66; } .neg { color:#d0503a; }
.hint { font-size:.78rem; opacity:.65; margin:8px 2px 0; }
.stats { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:4px 0 14px; }
.stat { border:1px solid rgba(128,128,128,.3); border-radius:12px; padding:10px 4px; text-align:center; }
.stat b { display:block; font-size:1.4rem; line-height:1.25; font-variant-numeric:tabular-nums; }
.stat span { font-size:.75rem; opacity:.65; }
.mc { display:grid; grid-template-columns:auto minmax(0,1fr) auto; gap:10px; align-items:center;
  border:1px solid rgba(128,128,128,.3); border-radius:12px; padding:10px 12px; }
.chip { min-width:38px; text-align:center; padding:3px 8px; border-radius:999px; font-weight:700; font-size:.85rem; color:#fff; }
.chip.w { background:#1b8f66; } .chip.l { background:#d0503a; } .chip.d { background:#1b6b4f; }
.mc .vs { overflow-wrap:anywhere; }
.mc .meta { font-size:.75rem; opacity:.65; }
.mc .sc { font-weight:800; font-size:1.3rem; font-variant-numeric:tabular-nums; }
.tag { display:inline-block; font-size:.68rem; padding:0 7px; border-radius:999px; border:1px solid rgba(128,128,128,.4); opacity:.8; margin-left:6px; }
.empty { padding:26px 12px; text-align:center; opacity:.65; border:1px dashed rgba(128,128,128,.4); border-radius:12px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------- 계산 ----------
def esc(text):
    return html.escape(str(text))


def nk(name):
    return "".join(unicodedata.normalize("NFC", str(name)).split())


def short_date(iso):
    try:
        y, m, d = str(iso).split("-")
        return f"{int(m)}/{int(d)}"
    except ValueError:
        return str(iso)


def signature(a, sa, b, sb, match_date):
    """두 선수, 날짜, 점수가 같으면 누가 기록했든 같은 서명이 나온다."""
    (k1, s1), (k2, s2) = sorted([(a, sa), (b, sb)], key=lambda t: t[0])
    return (k1, k2, str(match_date), s1, s2)


def build_groups(rows, me_id=None):
    """같은 경기를 한 묶음으로 만든다."""
    groups, order = {}, []
    for m in rows:
        a, b = m["writer_id"], m["opp_id"]
        sa, sb = int(m["my_score"]), int(m["opp_score"])
        sig = signature(a, sa, b, sb, m["match_date"])
        g = groups.get(sig)
        if g is None:
            g = {"sig": sig, "date": str(m["match_date"]), "a": a, "b": b, "sa": sa, "sb": sb,
                 "created": m.get("created_at", ""), "records": []}
            groups[sig] = g
            order.append(g)
        g["records"].append(m)
    for g in order:
        writers = []
        for r in g["records"]:
            if r["writer_id"] not in writers:
                writers.append(r["writer_id"])
        g["writers"] = writers
        g["confirmed"] = len(writers) > 1
        g["mine"] = next((r for r in g["records"] if r["writer_id"] == me_id), None) if me_id else None
    return order


RANK_BY = ["승수", "총득점"]


def compute_standings(groups, names, by="승수"):
    table = {}
    for g in groups:
        for pid, pf, pa in ((g["a"], g["sa"], g["sb"]), (g["b"], g["sb"], g["sa"])):
            r = table.setdefault(pid, {"id": pid, "name": names.get(pid, pid), "g": 0, "w": 0, "l": 0, "pf": 0, "pa": 0})
            r["g"] += 1
            r["pf"] += pf
            r["pa"] += pa
            if pf > pa:
                r["w"] += 1
            else:
                r["l"] += 1
    rows = list(table.values())
    for r in rows:
        r["rate"] = r["w"] / r["g"] if r["g"] else 0
        r["diff"] = r["pf"] - r["pa"]
    if by == "총득점":
        key = lambda r: (r["pf"], r["w"], r["diff"])
    else:
        key = lambda r: (r["w"], r["rate"], r["diff"], r["pf"])
    rows.sort(key=lambda r: tuple(-v for v in key(r)) + (r["name"],))
    rank = 0
    for i, r in enumerate(rows):
        p = rows[i - 1] if i else None
        tie = p and key(p) == key(r)
        if not tie:
            rank = i + 1
        r["rank"] = rank
    return rows


def pct(rate):
    return f"{round(rate * 100)}%"


def signed(n):
    return f"+{n}" if n > 0 else str(n)


# ---------- 화면 조각 ----------
def podium_html(rows, me_id, by="승수"):
    slots = []
    for idx in (1, 0, 2):
        r = rows[idx] if idx < len(rows) else None
        cls = f"slot p{idx + 1}" + ("" if r else " empty") + (" me" if r and r["id"] == me_id else "")
        medal = esc(r["rank"]) if r else "–"
        name = esc(r["name"]) if r else "대기 중"
        if not r:
            sub1 = sub2 = ""
        elif by == "총득점":
            sub1 = f"총득점 {r['pf']}점"
            sub2 = f"{r['w']}승 {r['l']}패 · 득실 {signed(r['diff'])}"
        else:
            sub1 = f"{r['w']}승 {r['l']}패"
            sub2 = f"승률 {pct(r['rate'])} · 득실 {signed(r['diff'])}"
        slots.append(
            f'<div class="{cls}"><div class="medal">{medal}</div><div class="nm">{name}</div>'
            f'<div class="sub">{sub1}</div><div class="sub">{sub2}</div><div class="blk">{idx + 1}</div></div>'
        )
    return f'<div class="pod">{"".join(slots)}</div>'


def rest_table_html(rows, me_id, by="승수"):
    rest = rows[3:]
    if not rest:
        return '<div class="empty">4위 이하 참가자는 아직 없습니다.</div>'
    out = [f'<div class="rt"><div class="r h"><span>순위</span><span>이름</span><span class="n">경기</span>'
           f'<span class="n">승</span><span class="n">패</span><span class="n">{"득점" if by == "총득점" else "승률"}</span><span class="n">득실</span></div>']
    for r in rest:
        cls = "r me" if r["id"] == me_id else "r"
        dcls = "pos" if r["diff"] > 0 else "neg" if r["diff"] < 0 else ""
        out.append(
            f'<div class="{cls}"><span class="rk">{esc(r["rank"])}</span><span>{esc(r["name"])}</span>'
            f'<span class="n">{r["g"]}</span><span class="n">{r["w"]}</span><span class="n">{r["l"]}</span>'
            f'<span class="n">{r["pf"] if by == "총득점" else pct(r["rate"])}</span><span class="n {dcls}">{signed(r["diff"])}</span></div>'
        )
    out.append("</div>")
    return "".join(out)


def my_card_html(g, me_id, names):
    mine_a = g["a"] == me_id
    my_s, op_s = (g["sa"], g["sb"]) if mine_a else (g["sb"], g["sa"])
    other = g["b"] if mine_a else g["a"]
    win = my_s > op_s
    tag = '<span class="tag">양쪽 기록 확인</span>' if g["confirmed"] else ""
    if g["mine"]:
        others = [names.get(w, w) for w in g["writers"] if w != me_id]
        who = "기록: 나" + (", " + ", ".join(others) if others else "")
        if not others:
            who = "내가 기록"
    else:
        who = "기록: " + ", ".join(names.get(w, w) for w in g["writers"])
    return (
        f'<div class="mc"><span class="chip {"w" if win else "l"}">{"승" if win else "패"}</span>'
        f'<div class="vs"><b>vs {esc(names.get(other, other))}</b>{tag}'
        f'<div class="meta">{esc(short_date(g["date"]))} · {esc(who)}</div></div>'
        f'<div class="sc">{my_s} : {op_s}</div></div>'
    )


def all_card_html(g, names):
    a_win = g["sa"] > g["sb"]
    w, l = (g["a"], g["b"]) if a_win else (g["b"], g["a"])
    tag = '<span class="tag">양쪽 기록 확인</span>' if g["confirmed"] else ""
    who = "기록: " + ", ".join(names.get(x, x) for x in g["writers"])
    return (
        f'<div class="mc"><span class="chip d">{esc(short_date(g["date"]))}</span>'
        f'<div class="vs"><b>{esc(names.get(w, w))}</b> 승 · {esc(names.get(l, l))} 패{tag}'
        f'<div class="meta">{esc(who)}</div></div>'
        f'<div class="sc">{max(g["sa"], g["sb"])} : {min(g["sa"], g["sb"])}</div></div>'
    )


# ---------- 저장소 ----------
try:
    ROSTER = store.roster()
except Exception:
    st.markdown('<div class="bn"><div class="t">우리 반 배드민턴 리그</div></div>', unsafe_allow_html=True)
    st.error("명단을 불러오지 못했습니다. Streamlit의 Secrets에 roster 항목이 있는지 확인하세요.")
    st.stop()

NAMES = {r["id"]: r["name"] for r in ROSTER}


def reason(exc):
    return str(exc) if isinstance(exc, store.StoreError) else "잠시 후 다시 시도하세요."


def load_matches():
    try:
        return store.matches()
    except Exception:
        return []


def today():
    return datetime.now(KST).date()


# ---------- 관리자 ----------
def kst_text(iso):
    try:
        return datetime.fromisoformat(str(iso)).astimezone(KST).strftime("%m/%d %H:%M")
    except ValueError:
        return str(iso)


def check_admin_password(typed):
    """맞으면 True, 틀리면 False, 비밀번호가 설정되지 않았으면 None."""
    try:
        expected = st.secrets.get("ADMIN_PASSWORD")
    except (KeyError, FileNotFoundError):
        expected = None
    if not expected:
        return None
    return hmac.compare_digest(str(typed).encode("utf-8"), str(expected).encode("utf-8"))


def admin_gate(key):
    """관리자 비밀번호 입력 칸. 이미 열려 있으면 True."""
    if st.session_state.get("admin"):
        return True
    tries = st.session_state.get("admin_fail", 0)
    with st.form(key):
        typed = st.text_input("관리자 비밀번호", type="password")
        pressed = st.form_submit_button("관리자 모드 열기")
    if pressed:
        if tries >= 5:
            st.error("비밀번호를 여러 번 틀렸습니다. 잠시 뒤 다시 시도하세요.")
        else:
            ok = check_admin_password(typed)
            if ok is None:
                st.error("관리자 비밀번호가 설정되지 않았습니다. Streamlit Secrets에 ADMIN_PASSWORD를 추가하세요.")
            elif ok:
                st.session_state.admin = True
                st.session_state.admin_fail = 0
                st.rerun()
            else:
                st.session_state.admin_fail = tries + 1
                st.error("비밀번호가 맞지 않습니다.")
    return False


def admin_logout():
    st.session_state.pop("admin", None)


def student_rows(groups, sid):
    """한 학생의 경기 목록(날짜 최신순). 같은 경기를 양쪽이 기록했어도 한 줄로 나온다."""
    mine = [g for g in groups if sid in (g["a"], g["b"])]
    mine.sort(key=lambda g: (g["date"], str(g["created"])), reverse=True)
    rows = []
    for g in mine:
        is_a = g["a"] == sid
        my_s, op_s = (g["sa"], g["sb"]) if is_a else (g["sb"], g["sa"])
        other = g["b"] if is_a else g["a"]
        rows.append({
            "학번": sid, "이름": NAMES.get(sid, sid),
            "경기 날짜": g["date"], "상대": f"{NAMES.get(other, other)}({other})",
            "점수": f"{my_s} : {op_s}", "경기 결과": "승" if my_s > op_s else "패",
        })
    return rows


def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")  # 엑셀에서 한글이 깨지지 않게


def admin_page():
    rows = load_matches()
    groups = build_groups(rows)
    standings = compute_standings(groups, NAMES)
    by_id = {r["id"]: r for r in standings}

    h1, h2 = st.columns([3, 2], vertical_alignment="center")
    h1.subheader("관리자 모드")
    h2.button("관리자 로그아웃", on_click=admin_logout, key="admin_out")

    ids = [m["id"] for m in ROSTER]
    pick = st.selectbox("학생 선택", ids, key="admin_student",
                        format_func=lambda i: f"{i}  {NAMES[i]}")
    st.caption(f"전체 {len(groups)}경기, 원본 기록 {len(rows)}건")

    # 선택한 학생이 상대별로 치른 경기: 학번 순서대로 한 줄씩, 아직 없으면 빈칸
    played = {}
    for row in reversed(student_rows(groups, pick)):  # 날짜 오래된 순
        oid = row["상대"].rsplit("(", 1)[-1].rstrip(")")
        played.setdefault(oid, []).append(row)
    table, wins, losses = [], 0, 0
    for m in ROSTER:
        games = played.get(m["id"], []) if m["id"] != pick else []
        if not games:
            table.append({"상대 선수": f'{m["id"]} {m["name"]}', "경기 날짜": "", "점수": "", "경기 결과": ""})
            continue
        for g in games:
            wins += g["경기 결과"] == "승"
            losses += g["경기 결과"] == "패"
            table.append({"상대 선수": f'{m["id"]} {m["name"]}', "경기 날짜": short_date(g["경기 날짜"]),
                          "점수": g["점수"], "경기 결과": g["경기 결과"]})
    df = pd.DataFrame(table)
    st.markdown(f"#### {esc(NAMES[pick])} ({esc(pick)})", unsafe_allow_html=True)
    st.dataframe(df, hide_index=True, height=35 * (len(df) + 1) + 3)
    st.markdown(f"**총 {wins}승 {losses}패**")
    st.download_button(f"{NAMES[pick]} 기록 내려받기(CSV)", csv_bytes(df),
                       f"badminton_{pick}_{NAMES[pick]}.csv", "text/csv", key=f"dl_{pick}")

    st.button("새로고침", on_click=store.matches.clear, key="admin_refresh")


# ---------- 로그인 ----------
def find_member(student_id, name):
    sid = str(student_id).strip()
    for r in ROSTER:
        if r["id"] == sid and nk(r["name"]) == nk(name):
            return r
    return None


COOKIE = "bl_user"


def saved_login():
    """주소의 ?id=&name= 또는 이 기기에 저장된 쿠키에서 이전 로그인 정보를 찾는다."""
    qp = st.query_params
    if qp.get("id") and qp.get("name"):
        return qp.get("id"), qp.get("name")
    try:
        raw = unquote(st.context.cookies.get(COOKIE, ""))
    except Exception:
        return None
    if "|" in raw:
        sid, name = raw.split("|", 1)
        return sid, name
    return None


def run_js(code):
    page = f"<script>try{{{code}}}catch(e){{}}</script>"
    if hasattr(st, "iframe"):  # components.html은 최신 Streamlit에서 사라진다
        st.iframe(page, height=1)
    else:
        components.html(page, height=0)


def browser_cookie(value):
    """이 기기의 브라우저에 로그인 정보를 저장(value가 None이면 삭제)한다. 쿠키와 localStorage에 함께 둔다."""
    if value is None:
        run_js(f'var w=window.parent;w.document.cookie="{COOKIE}=; max-age=0; path=/; SameSite=Lax";'
               f'w.localStorage.removeItem("{COOKIE}");')
    else:
        v = value.replace("\\", "\\\\").replace('"', '\\"')
        run_js(f'var w=window.parent;w.document.cookie="{COOKIE}={quote(value)}; max-age=15552000; path=/; SameSite=Lax; Secure";'
               f'w.localStorage.setItem("{COOKIE}","{v}");')


def restore_from_browser():
    """저장된 정보가 있으면 주소에 ?id=&name=을 붙여 다시 열어, 기존 주소 로그인으로 입장시킨다."""
    run_js(f'var w=window.parent;var v=w.localStorage.getItem("{COOKIE}");var u=new URL(w.location.href);'
           'if(v&&v.indexOf("|")>0&&!u.searchParams.get("id")){var i=v.indexOf("|");'
           'u.searchParams.set("id",v.slice(0,i));u.searchParams.set("name",v.slice(i+1));w.location.replace(u.toString());}')


if "me" not in st.session_state and not st.session_state.get("no_auto"):
    found = saved_login()
    if found:
        member = find_member(*found)
        if member:
            st.session_state.me = {"id": member["id"], "name": member["name"]}

st.markdown('<div class="bn"><div class="t">우리 반 배드민턴 리그</div></div>', unsafe_allow_html=True)

if "me" not in st.session_state:
    if st.session_state.get("admin"):
        admin_page()
        st.stop()
    if st.session_state.pop("clear_cookie", False):
        browser_cookie(None)
    elif not st.session_state.get("no_auto"):
        restore_from_browser()
    with st.form("login"):
        st.subheader("로그인")
        st.caption("반 명단에 있는 학번과 이름으로만 입장할 수 있습니다.")
        sid_in = st.text_input("학번", placeholder="예: 21218", max_chars=12)
        name_in = st.text_input("이름", placeholder="예: 홍길동", max_chars=20)
        submitted = st.form_submit_button("입장하기", type="primary")
    if submitted:
        member = find_member(sid_in, name_in)
        if member:
            st.session_state.me = {"id": member["id"], "name": member["name"]}
            st.session_state.pop("no_auto", None)
            st.session_state.save_cookie = True
            st.query_params["id"] = member["id"]
            st.query_params["name"] = member["name"]
            st.rerun()
        else:
            st.error("명단에 없는 학번 또는 이름입니다. 학번과 이름을 다시 확인하세요.")
    with st.expander("관리자 로그인"):
        admin_gate("admin_gate_login")
    st.stop()

ME = st.session_state.me
if not st.session_state.get("cookie_saved"):
    browser_cookie(f"{ME['id']}|{ME['name']}")
    st.session_state.cookie_saved = True
st.session_state.pop("save_cookie", None)


def logout():
    for k in ("me", "cookie_saved", "editing", "armed", "flash", "f_date", "f_opp", "f_my", "f_op"):
        st.session_state.pop(k, None)
    st.session_state.no_auto = True
    st.session_state.clear_cookie = True
    st.query_params.clear()


c1, c2 = st.columns([4, 1], vertical_alignment="center")
c1.markdown(f"**{esc(ME['name'])}** · 학번 {esc(ME['id'])}")
c2.button("로그아웃", on_click=logout)

# ---------- 기록 입력 ----------
st.session_state.setdefault("f_date", today())
st.session_state.setdefault("f_opp", None)
st.session_state.setdefault("f_my", None)
st.session_state.setdefault("f_op", None)
st.session_state.setdefault("editing", None)
st.session_state.setdefault("armed", None)


def reset_form():
    st.session_state.f_date = today()
    st.session_state.f_opp = None
    st.session_state.f_my = None
    st.session_state.f_op = None
    st.session_state.editing = None


def flash(kind, text):
    st.session_state.flash = (kind, text)


def submit_match():
    s = st.session_state
    d, opp, my, op = s.f_date, s.f_opp, s.f_my, s.f_op
    if not d or not opp or my is None or op is None:
        return flash("error", "모든 항목을 입력하세요.")
    my, op = int(my), int(op)
    if not (0 <= my <= 99 and 0 <= op <= 99):
        return flash("error", "점수는 0 이상 99 이하의 정수로 입력하세요.")
    if my == op:
        return flash("error", "배드민턴은 무승부가 없습니다. 점수를 확인하세요.")
    if opp == ME["id"] or opp not in NAMES:
        return flash("error", "상대는 본인이 아닌 명단의 다른 사람이어야 합니다.")

    editing = s.editing
    try:
        rows = [r for r in store.matches() if r["id"] != editing]
    except Exception as exc:
        return flash("error", "기록을 불러오지 못했습니다. " + reason(exc))
    sig = signature(ME["id"], my, opp, op, d.isoformat())
    same = [r for r in rows if signature(r["writer_id"], int(r["my_score"]), r["opp_id"], int(r["opp_score"]), r["match_date"]) == sig]
    if any(r["writer_id"] == ME["id"] for r in same):
        return flash("error", "이미 같은 경기를 기록했습니다. 목록에서 확인하세요.")
    note = " 상대가 기록한 같은 경기와 한 경기로 합쳐졌습니다." if same else ""

    row = {"writer_id": ME["id"], "opp_id": opp, "match_date": d.isoformat(), "my_score": my, "opp_score": op}
    try:
        if editing:
            if not store.update_match(editing, ME["id"], row):
                return flash("error", "수정하지 못했습니다. 이미 삭제된 기록일 수 있습니다.")
            flash("success", "경기 기록을 수정했습니다." + note)
        else:
            store.add_match(row)
            flash("success", "경기 기록을 추가했습니다." + note)
    except Exception as exc:
        return flash("error", "저장에 실패했습니다. " + reason(exc))
    reset_form()


def start_edit(rec):
    s = st.session_state
    s.f_date = date.fromisoformat(str(rec["match_date"]))
    s.f_opp = rec["opp_id"]
    s.f_my = int(rec["my_score"])
    s.f_op = int(rec["opp_score"])
    s.editing = rec["id"]
    s.armed = None


def cancel_edit():
    reset_form()


def delete_record(rec):
    s = st.session_state
    if s.armed != rec["id"]:
        s.armed = rec["id"]
        return
    s.armed = None
    try:
        if store.delete_match(rec["id"], ME["id"]):
            if s.editing == rec["id"]:
                reset_form()
            flash("success", "경기 기록을 삭제했습니다.")
        else:
            flash("error", "삭제하지 못했습니다. 이미 지워진 기록이거나 내가 쓴 기록이 아닙니다.")
    except Exception as exc:
        flash("error", "삭제하지 못했습니다. " + reason(exc))


# ---------- 탭 ----------
tab_rank, tab_mine, tab_all = st.tabs(["순위", "내 기록", "전체 경기"])


@st.fragment(run_every=15)
def rank_view():
    by = st.radio("순위 기준", RANK_BY, horizontal=True, key="rank_by")
    groups = build_groups(load_matches())
    rows = compute_standings(groups, NAMES, by)
    st.markdown(podium_html(rows, ME["id"], by), unsafe_allow_html=True)
    if not rows:
        st.markdown('<div class="empty">아직 등록된 경기가 없습니다. 내 기록 탭에서 첫 경기를 기록해 보세요.</div>', unsafe_allow_html=True)
    else:
        st.markdown(rest_table_html(rows, ME["id"], by), unsafe_allow_html=True)
    rule = "총득점, 승수, 득실차 순" if by == "총득점" else "승수, 승률, 득실차, 총득점 순"
    st.markdown(f'<div class="hint">정렬 기준: {rule}. 양쪽이 모두 기록해도 날짜, 상대, 점수가 같으면 한 경기로 계산됩니다. 15초마다 자동으로 갱신됩니다.</div>', unsafe_allow_html=True)


@st.fragment(run_every=15)
def all_view():
    groups = build_groups(load_matches())
    groups.sort(key=lambda g: (g["date"], str(g["created"])), reverse=True)
    if not groups:
        st.markdown('<div class="empty">아직 등록된 경기가 없습니다.</div>', unsafe_allow_html=True)
    for g in groups:
        st.markdown(all_card_html(g, NAMES), unsafe_allow_html=True)


with tab_rank:
    rank_view()

with tab_mine:
    all_groups = build_groups(load_matches(), ME["id"])
    standings = compute_standings(all_groups, NAMES)
    me_row = next((r for r in standings if r["id"] == ME["id"]), None)
    if me_row:
        vals = [(f"{me_row['rank']}위", "순위"), (f"{me_row['w']}승 {me_row['l']}패", "전적"), (pct(me_row["rate"]), "승률"),
                (str(me_row["pf"]), "총득점"), (str(me_row["pa"]), "총실점"), (signed(me_row["diff"]), "득실차")]
    else:
        vals = [("–", "순위"), ("0승 0패", "전적"), ("–", "승률"), ("0", "총득점"), ("0", "총실점"), ("–", "득실차")]
    st.markdown('<div class="stats">' + "".join(f"<div class='stat'><b>{esc(v)}</b><span>{esc(k)}</span></div>" for v, k in vals) + "</div>", unsafe_allow_html=True)

    fl = st.session_state.pop("flash", None)
    if fl:
        (st.success if fl[0] == "success" else st.error)(fl[1])

    editing = st.session_state.editing
    with st.form("match_form", border=True):
        st.subheader("경기 기록 수정" if editing else "경기 결과 기록")
        st.date_input("경기 날짜", key="f_date")
        options = [r["id"] for r in ROSTER if r["id"] != ME["id"]]
        st.selectbox("상대 선택", options, index=None, key="f_opp", placeholder="상대를 선택하세요",
                     format_func=lambda i: f"{NAMES[i]}({i})")
        s1, s2 = st.columns(2)
        s1.number_input("내 점수", min_value=0, max_value=99, step=1, value=None, key="f_my", placeholder="0")
        s2.number_input("상대 점수", min_value=0, max_value=99, step=1, value=None, key="f_op", placeholder="0")
        st.form_submit_button("수정 저장" if editing else "기록 추가", type="primary", on_click=submit_match)
    if editing:
        st.button("수정 취소", on_click=cancel_edit)

    st.subheader("내 경기 기록")
    mine = [g for g in all_groups if ME["id"] in (g["a"], g["b"])]
    mine.sort(key=lambda g: (g["date"], str(g["created"])), reverse=True)
    if not mine:
        st.markdown('<div class="empty">아직 기록한 경기가 없습니다.</div>', unsafe_allow_html=True)
    for g in mine:
        st.markdown(my_card_html(g, ME["id"], NAMES), unsafe_allow_html=True)
        rec = g["mine"]
        if rec:
            b1, b2, _ = st.columns([1, 1, 3])
            b1.button("수정 중" if editing == rec["id"] else "수정", key=f"e_{rec['id']}", on_click=start_edit, args=(rec,))
            armed = st.session_state.armed == rec["id"]
            b2.button("정말 삭제" if armed else "삭제", key=f"d_{rec['id']}", on_click=delete_record, args=(rec,),
                      type="primary" if armed else "secondary")
    st.button("새로고침", on_click=store.matches.clear)

with tab_all:
    all_view()
