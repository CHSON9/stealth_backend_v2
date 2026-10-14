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
