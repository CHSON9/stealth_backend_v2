import base64
import os
import cv2
import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flasgger import Swagger
from flask_cors import CORS
from back_api import api_bp, get_db_connection
from app.identity import FaceRecognizer
from app.vision import TargetPreservingPipeline
from main import RTX3090_BUFFERED_RUNTIME


app = Flask(__name__)
app.config['SECRET_KEY'] = 'stealth_secret_key'
CORS(app, resources={r"/api/*": {"origins": "*"}})

# CORS 및 Socket.io 설정
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10 * 1024 * 1024, always_connect=True)
swagger = Swagger(app)

app.register_blueprint(api_bp)

@app.route('/sender')
def render_sender():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(BASE_DIR, 'sender.html')

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(os.path.join(BASE_DIR, 'uploads'), filename)

# -------------------------------------------------------------------
# 글로벌 AI 파이프라인 및 상태 관리
# -------------------------------------------------------------------
GALLERY_PATH = "data/target_face_embeddings.npz"
recognizer = None
pipeline = None

def init_ai_pipeline():
    global recognizer, pipeline
    print("\n[AI Server] 🤖 TargetPreservingPipeline 초기화 시작...")
    
    if not os.path.exists(GALLERY_PATH):
        os.makedirs(os.path.dirname(GALLERY_PATH), exist_ok=True)
        np.savez_compressed(GALLERY_PATH, embeddings=np.empty((0, 0), dtype=np.float32), person_ids=np.empty((0,), dtype=str))

    recognizer = FaceRecognizer(gallery_path=GALLERY_PATH, threshold=0.42)

    runtime_config = RTX3090_BUFFERED_RUNTIME.copy()
    
    pipeline = TargetPreservingPipeline(
        recognizer=recognizer,
        model_path="yolov8n-seg.pt",
        device="0",  
        confidence=0.18,
        use_lama=False,
        show_debug=False,
        runtime=runtime_config,
        mode="preserve-target"
    )
    
    print("[AI Server] 🔥 GPU 및 ONNX 모델 워밍업 수행 중 (480x640)...")
    pipeline.warmup_live(height=480, width=640, frames=10)
    print("[AI Server] ✅ AI 파이프라인 준비 완료!\n")


# -------------------------------------------------------------------
# Socket.IO 실시간 통신 이벤트 핸들러
# -------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    print(f"[Socket.IO] 클라이언트 연결됨: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    global is_streaming
    print(f"[Socket.IO] 클라이언트 연결 해제됨: {request.sid}")
    is_streaming = False
    socketio.emit('stream_status', {'status': 'stopped'}, room='viewer')

is_streaming = False

@socketio.on('register_client')
def handle_register_client(data):
    """
    클라이언트 역할 등록 (sender: 폰 송출자 / viewer: 노트북 시청자)
    """
    role = data.get('role', 'viewer')
    join_room(role)
    print(f"[Socket.IO] 기기 등록 완료 - SID: {request.sid}, Role: {role}")
    initial_status = 'streaming' if is_streaming else 'waiting'
    emit('stream_status', {'status': initial_status}, room=request.sid)

is_processing = False

@socketio.on('image_frame')
def handle_image_frame(data):
    """
    폰(sender)으로부터 원본 프레임을 수신받아 AI 가공 후 시청자(viewer)로 전송
    """
    global pipeline, is_streaming, is_processing
    try:
        image_data = data.get('image')

        if not image_data:
            return

        emit('original_frame', {
            'original_image': image_data,
        }, room='viewer')

        if not is_streaming:
            is_streaming = True
            socketio.emit('stream_status', {'status': 'streaming'}, room='viewer')

        if is_processing:
            return

        is_processing = True

        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        img_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is not None:
            socketio.sleep(0)
            result_frame, stats = pipeline.process(frame)

            _, buffer = cv2.imencode('.jpg', result_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            encoded_result = base64.b64encode(buffer).decode('utf-8')
            result_base64 = f"data:image/jpeg;base64,{encoded_result}"

            emit('processed_frame', {
                'result_image': result_base64
                }, room='viewer')

    except Exception as e:
        print(f"[Socket.IO Error] 프레임 처리 실패: {e}")
        emit('stream_error', {
            'code': 'PROCESSING_FAILED',
            'message': f'AI 프레임 가공 실패: {str(e)}'
        }, room=request.sid)
    finally:
        is_processing = False


# -------------------------------------------------------------------
# 신규 인물 등록 시 갤러리 갱신 내부 헬퍼 (REST API 연동용)
# -------------------------------------------------------------------
def reload_gallery_embeddings(person_id, image_paths):
    """
    REST API POST /api/persons 에서 호출하여 신규 인물 얼굴을 FaceRecognizer에 바로 등록
    """
    global recognizer, pipeline
    try:
        print(f"[AI Sync] 신규 인물 '{person_id}' 얼굴 임베딩 등록 중...")
        count = recognizer.enroll(image_paths, person_id=person_id, append=True)
        pipeline.reset_stream()
        print(f"[AI Sync] 성공! {count}개의 얼굴 임베딩이 갤러리에 추가되었습니다.")
        return True
    except Exception as e:
        print(f"[AI Sync Error] 갤러리 임베딩 등록 실패: {e}")
        return False


if __name__ == '__main__':
    init_ai_pipeline()

    print("=" * 60)
    print("🚀 이동형 비전 시스템 백엔드 통합 서버 가동")
    print("  - REST API & Swagger UI: http://127.0.0.1:5000/apidocs/")
    print("  - Socket.IO 실시간 통신 : ws://127.0.0.1:5000")
    print("=" * 60 + "\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False)