# STEALTH Vision Backend Server

### 1. 백엔드 파일 구성
- `back_server.py` : 메인 백엔드 통합 서버 (Socket.IO & Flask)
- `back_api.py` : REST API 블루프린트 명세 및 DB 라우트
- `sender.html` : 모바일 카메라 송출용 웹뷰

---

### 2. 실행 전 필수 준비
기존에 공유된 **AI 알고리즘 모듈(`app/`, `main.py`, `yolov8n-seg.pt` 등)**이 동일한 프로젝트 루트 폴더에 위치.

---

### 3. IP 주소 변경 안내
서버를 다른 IP 환경에서 테스트할 경우, 아래 2개 파일의 IP 주소를 본인 IP로 변경(SERVER_BASE_URL 변수 수정, SERVER_URL 변수 수정)
- `back_api.py` : SERVER_BASE_URL = "http://[YOUR_SERVER_IP]:5000"
- `sender.html` : const SERVER_URL = "http://[YOUR_SERVER_IP]:5000";

---

### 4. 이미지 폴더 구성 (`uploads/`) 안내
- 현재 `uploads/persons/` 하위 `person_01`, `person_02`, `person_03` 폴더에 각각 예시 이미지 1장씩 배치되어 있음
- 백엔드 서버 코드(`back_server.py`)가 해당 `uploads/` 디렉토리 내부에서 사진 파일을 읽어 오도록 구현되어 있으므로, **모델 학습 및 테스트 시 실제 사용될 이미지 파일로 변경/추가 배치**

---

### 5. 데이터베이스(DB) 복원 안내
- 프로젝트에 포함된 DB 덤프 파일(`dump.sql`)을 사용하여 MySQL DB를 구축
- **테이블 생성 순서**: 외래키(FK) 참조 관계에 의해 반드시 **`persons` (부모 테이블) ➔ `person_photos` (자식 테이블)** 순서로 생성 및 데이터가 입력되어야 함
- `sessions` 테이블은 세션 관리용 보조 테이블이므로 무시해도 무방함
