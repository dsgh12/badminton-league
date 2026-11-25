# 우리 반 배드민턴 리그

학번과 이름으로 입장해 경기 결과를 기록하고, 순위를 한눈에 보는 Streamlit 웹앱이다. 화면은 Streamlit Community Cloud, 기록은 GitHub 비공개 저장소의 파일 하나에 저장한다. GitHub와 Streamlit 외에 다른 서비스는 쓰지 않는다.

## 주요 기능
- 반 명단에 있는 학번과 이름으로 입장
- 내 기록 탭: 경기 날짜, 상대(명단에서 선택), 점수 입력, 수정, 삭제, 내 전적 요약
- 순위 탭: 1~3등 시상대, 4등 이하 표, 15초마다 자동 갱신
- 전체 경기 탭: 반 전체 경기 기록
- 날짜, 두 선수, 점수가 같은 기록은 누가 썼든 한 경기로 계산
- 관리자 모드: 학생별 요약, 학생별 전체 기록, 원본 기록 표와 CSV 내려받기 (비밀번호는 Secrets의 `ADMIN_PASSWORD`)

## 구조
- 앱 저장소(공개 가능): `app.py`, `store.py`, `requirements.txt`, 이 README. 이름과 토큰은 들어 있지 않다.
- 데이터 저장소(비공개): `matches.json` 한 파일에 학번과 점수만 저장된다. 기록을 바꿀 때마다 커밋이 쌓여서 잘못된 내용을 이전 커밋으로 되돌릴 수 있다.
- 명단과 토큰: Streamlit의 Secrets 칸에만 둔다.

## 설정 순서
1. **데이터 저장소 만들기**: GitHub에서 새 저장소를 만든다. 이름은 `badminton-data`, 공개 범위는 **Private**, `Add a README file`을 체크한다.
2. **토큰 만들기**: GitHub 프로필, Settings, Developer settings, Personal access tokens, Fine-grained tokens, Generate new token. Repository access는 `Only select repositories`로 `badminton-data`만 고르고, Permissions의 `Contents`를 `Read and write`로 정한다. 만료일은 학기 끝까지로 정하고 토큰을 복사한다.
3. **앱 저장소 만들기**: 새 저장소를 만들고 `app.py`, `store.py`, `requirements.txt`, `README.md`, `.gitignore`, `.streamlit/secrets.toml.example`을 올린다. 명단이 든 `secrets_to_paste.toml`은 올리지 않는다.
4. **Streamlit 배포**: share.streamlit.io에서 Create app, 앱 저장소, 브랜치 main, 파일 `app.py`를 고른다. Advanced settings의 Secrets 칸에 `secrets_to_paste.toml` 내용을 붙여넣는다. 토큰과 `내아이디/badminton-data` 부분만 바꾼다. Deploy를 누른다.

## 관리자 비밀번호 바꾸기
비밀번호는 코드가 아니라 Streamlit의 Secrets에 있다. 앱 Settings, Secrets에서 `ADMIN_PASSWORD = "새 비밀번호"` 줄을 고치고 Save를 누르면 바로 바뀐다. 이 줄은 `[[roster]]`보다 위쪽에 둔다. 코드를 고칠 필요는 없다.

## 알아둘 점
- 한동안 접속이 없으면 Streamlit 앱이 잠들 수 있다. 화면의 버튼을 누르면 다시 켜진다.
- 토큰이 만료되면 기록을 불러오지 못한다. 새 토큰을 만들어 Secrets의 `GITHUB_TOKEN`만 바꾸면 된다.
- 여러 명이 동시에 저장하면 서버가 자동으로 다시 시도한다.
- 입장하면 주소에 학번과 이름이 붙어 새로고침해도 로그인이 유지된다. 그 주소를 다른 사람에게 보내면 그 사람이 내 이름으로 입장할 수 있으니 공유하지 않는다.
