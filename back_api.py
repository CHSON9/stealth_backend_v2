import sys
from flask import Blueprint, request, jsonify
import mysql.connector
import os
import uuid
from werkzeug.utils import secure_filename

#db 연결
def get_db_connection():
    connection = mysql.connector.connect(
        host='127.0.0.1',       
        user='root',            
        password='mysql1234', 
        database='stealth_db',  
        buffered=True,
        autocommit=True
    )
    if not connection.is_connected():
        connection.reconnect(attempts=3, delay=1)
    return connection

api_bp = Blueprint('stealth_api', __name__)
SERVER_BASE_URL = "http://119.194.117.120:5000" #환경 바뀔 때 변경

# -------------------------------------------------------------------
# REST API 1. 등록 인물 목록 조회
# -------------------------------------------------------------------
@api_bp.route('/api/persons', methods=['GET'])
def get_persons():
    """
    등록 인물 목록 조회 API
    ---
    tags:
      - Persons
    description: 사전 등록된 인물 3명(채현, 은아, 혜민)의 기본 정보 및 대표 사진 URL을 조회
    responses:
      200:
        description: 인물 목록 조회 성공
        schema:
          properties:
            status:
              type: string
              example: "success"
            persons:
              type: array
              items:
                properties:
                  person_id:
                    type: string
                    example: "person_01"
                  name:
                    type: string
                    example: "채현"
                  representative_image_url:
                    type: string
                    example: "/uploads/persons/chaehyeon_rep.jpg"
      500:
        description: 서버 내부 에러
    """
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # persons 테이블에서 인물 목록 및 대표 사진 경로를 함께 가져옴
        sql = """
            SELECT 
                p.person_id,
                p.name,
                IFNULL(MAX(pp.image_path), '') AS representative_image_url
            FROM persons p
            LEFT JOIN person_photos pp 
                   ON p.person_id = pp.person_id AND pp.is_representative = 1
            GROUP BY p.person_id, p.name
            ORDER BY p.person_id ASC
        """
        cursor.execute(sql)
        persons = cursor.fetchall()

        for p in persons:
            if p.get('representative_image_url'):
                p['representative_image_url'] = f"{SERVER_BASE_URL}{p['representative_image_url']}"
        
        return jsonify({
            "status": "success",
            "data": persons,
            "persons": persons
        }), 200
        
    except Exception as e:
        print(f"[API Error] 등록 인물 목록 조회 실패: {e}")
        return jsonify({
            "code": "SERVER_ERROR",
            "message": f"서버 내부 오류가 발생: {str(e)}"
        }), 500
    finally:
        cursor.close()
        db.close()


# -------------------------------------------------------------------
# REST API 2. 인물별 등록 사진 조회
# -------------------------------------------------------------------
@api_bp.route('/api/persons/<string:person_id>/photos', methods=['GET'])
def get_person_photos(person_id):
    """
    인물별 등록 사진 조회 API
    ---
    tags:
      - Persons
    description: 선택한 인물(person_id)의 등록된 전체 사진(20~30장) 목록을 조회
    parameters:
      - name: person_id
        in: path
        type: string
        required: true
        description: 조회할 인물의 고유 식별자 (예; person_01)
    responses:
      200:
        description: 사진 목록 조회 성공
        schema:
          properties:
            status:
              type: string
              example: "success"
            person_id:
              type: string
              example: "person_01"
            name:
              type: string
              example: "채현"
            photos:
              type: array
              items:
                properties:
                  photo_id:
                    type: string
                    example: "photo_01"
                  image_url:
                    type: string
                    example: "/uploads/persons/chaehyeon_01.jpg"
                  is_representative:
                    type: boolean
                    example: true
      404:
        description: 해당 인물을 찾을 수 없음
      500:
        description: 서버 내부 에러
    """
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        # 1. 대상 인물 존재 여부 및 이름 확인
        person_sql = "SELECT person_id, name FROM persons WHERE person_id = %s"
        cursor.execute(person_sql, (person_id,))
        person = cursor.fetchone()
        
        if not person:
            return jsonify({
                "code": "PERSON_NOT_FOUND",
                "message": "해당 인물 정보를 찾을 수 없습니다."
            }), 404
            
        # 2. 해당 인물의 등록 사진 전체 목록 조회
        photos_sql = """
            SELECT 
                photo_id,
                image_path AS image_url,
                is_representative
            FROM person_photos
            WHERE person_id = %s
            ORDER BY is_representative DESC, photo_id ASC
        """
        cursor.execute(photos_sql, (person_id,))
        photos = cursor.fetchall()

        for photo in photos:
            photo['is_representative'] = bool(photo['is_representative'])
            if photo.get('image_url'):
                photo['image_url'] = f"{SERVER_BASE_URL}{photo['image_url']}"
        
        return jsonify({
            "status": "success",
            "person_id": person['person_id'],
            "name": person['name'],
            "photos": photos
        }), 200
        
    except Exception as e:
        print(f"[API Error] 인물별 사진 조회 실패: {e}")
        return jsonify({
            "code": "SERVER_ERROR",
            "message": f"서버 내부 오류가 발생: {str(e)}"
        }), 500
    finally:
        cursor.close()
        db.close()


# -------------------------------------------------------------------
# REST API 3. [신규 추가] 인물 신규 등록 (이름 + 사진 파일 복수 업로드)
# -------------------------------------------------------------------
UPLOAD_FOLDER = 'uploads/persons'

@api_bp.route('/api/persons', methods=['POST'])
def create_person():
    """
    인물 신규 등록 API
    ---
    tags:
      - Persons
    description: 새로운 인물의 이름과 사진 파일들(20~30장)을 multipart/form-data로 받아 서버 및 DB에 신규 등록
    consumes:
      - multipart/form-data
    parameters:
      - name: name
        in: formData
        type: string
        required: true
        description: 등록할 인물의 이름 (예; 채현)
      - name: photos
        in: formData
        type: file
        required: true
        description: 업로드할 인물 사진 파일들 (다중 선택 가능)
    responses:
      201:
        description: 인물 등록 성공
      400:
        description: 필수 입력값 또는 유효한 파일 누락
      500:
        description: 서버 내부 에러
    """
    name = request.form.get('name')
    files = request.files.getlist('photos') or request.files.getlist('photo')
    
    valid_files = [f for f in files if f and f.filename != '']
    if not name or not valid_files:
        return jsonify({"code": "INVALID_INPUT", "message": "이름과 하나 이상의 사진을 첨부해야 합니다."}), 400
        
    db = get_db_connection()
    cursor = db.cursor()
    try:
        person_id = f"person_{uuid.uuid4().hex[:8]}"

        cursor.execute("INSERT INTO persons (person_id, name) VALUES (%s, %s)", (person_id, name))

        person_dir = os.path.join(UPLOAD_FOLDER, person_id)
        os.makedirs(person_dir, exist_ok=True)
        
        for idx, file in enumerate(valid_files):
            original_filename = secure_filename(file.filename)

            if not original_filename:
                ext = os.path.splitext(file.filename)[1] or '.jpg'
                original_filename = f"image{ext}"

            unique_filename = f"{uuid.uuid4().hex[:6]}_{original_filename}"

            photo_id = f"photo_{uuid.uuid4().hex[:8]}"
            save_path = os.path.join(person_dir, unique_filename)
            file.save(save_path)
            
            web_image_path = f"/uploads/persons/{person_id}/{unique_filename}"
            is_rep = 1 if idx == 0 else 0
            
            cursor.execute("""
                INSERT INTO person_photos (photo_id, person_id, image_path, is_representative)
                VALUES (%s, %s, %s, %s)
            """, (photo_id, person_id, web_image_path, is_rep))
            
        db.commit()

        try:
            server_module = sys.modules.get('__main__') or sys.modules.get('back_server')
    
            if server_module and hasattr(server_module, 'reload_gallery_embeddings'):
                actual_paths = [os.path.join(person_dir, fname) for fname in os.listdir(person_dir)]
                if actual_paths:
                    server_module.reload_gallery_embeddings(person_id, actual_paths)
            else:
                print(f"[AI Sync Info] reload_gallery_embeddings 함수를 찾을 수 없어 AI 갤러리 갱신을 건너뜁니다.")
        except Exception as sync_err:
            print(f"[AI Sync Warning] 갤러리 동기화 중 오류 (서버 미가동 등): {sync_err}")

        return jsonify({
            "status": "success",
            "message": "인물이 성공적으로 추가되었습니다.",
            "person_id": person_id
        }), 201
        
    except Exception as e:
        db.rollback()
        return jsonify({"code": "SERVER_ERROR", "message": str(e)}), 500
    finally:
        cursor.close()
        db.close()


# -------------------------------------------------------------------
# REST API 4. [신규 추가] 대표 사진 변경
# -------------------------------------------------------------------
@api_bp.route('/api/photos/<string:photo_id>/representative', methods=['PATCH'])
def update_representative_photo(photo_id):
    """
    대표 사진 변경 API
    ---
    tags:
      - Photos
    description: 선택한 사진(photo_id)을 인물의 새로운 대표 사진으로 지정
    parameters:
      - name: photo_id
        in: path
        type: string
        required: true
        description: 대표 사진으로 지정할 사진의 photo_id
    responses:
      200:
        description: 대표 사진 변경 성공
      404:
        description: 해당 사진을 찾을 수 없음
      500:
        description: 서버 내부 에러
    """
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT person_id FROM person_photos WHERE photo_id = %s", (photo_id,))
        photo = cursor.fetchone()
        
        if not photo:
            return jsonify({"code": "PHOTO_NOT_FOUND", "message": "해당 사진을 찾을 수 없습니다."}), 404
            
        person_id = photo['person_id']
        
        cursor.execute("UPDATE person_photos SET is_representative = 0 WHERE person_id = %s", (person_id,))
        
        cursor.execute("UPDATE person_photos SET is_representative = 1 WHERE photo_id = %s AND person_id = %s", (photo_id, person_id))

        db.commit()
        return jsonify({"status": "success", "message": "대표 사진이 변경되었습니다."}), 200
        
    except Exception as e:
        db.rollback()
        return jsonify({"code": "SERVER_ERROR", "message": str(e)}), 500
    finally:
        cursor.close()
        db.close()

# -------------------------------------------------------------------
# Socket.io 실시간 통신 명세서 (Swagger 전용 페이지)
# -------------------------------------------------------------------
@api_bp.route('/socket_docs')
def socket_docs():
    """
    실시간 통신 (Socket.io) 명세서
    ---
    tags:
      - Real-time (Socket.io)
    description: |
      이 섹션은 2학기 이동형 카메라 투명화 비전 시스템의 Socket.io 이벤트를 정의
      
      ### [1] 클라이언트 -> 서버 (Client -> Server Events)
      
      1. **`register_client`**
         - **설명**: 프론트 접속 시 기기 역할(핸드폰/노트북)을 등록
         - **데이터 규격**:
           ```json
           {
             "role": "sender" // 핸드폰(송출자)일 경우 "sender", 노트북(시청자)일 경우 "viewer"
           }
           ```
         
      2. **`image_frame`**
         - **설명**: 핸드폰 카메라 웹뷰에서 원본 이미지 프레임을 초당 송출
         - **데이터 규격**:
           ```json
           {
             "image": "data:image/jpeg;base64,.....(Base64 문자열)"
           }
           ```
           
      ---
      
      ### [2] 서버 -> 클라이언트 (Server -> Client Events)
      
      1. **`original_frame`** [신규]
         - **설명**: 핸드폰에서 올라온 원본 프레임을 시청자(`viewer`) 화면(왼쪽)으로 바로 중계(Relay)
         - **데이터 규격**:
           ```json
           {
             "original_image": "data:image/jpeg;base64,.....(Base64 문자열)"
           }
           ```

      2. **`processed_frame`**
         - **설명**: AI 파이프라인에서 투명화/배경복원이 완료된 처리 영상 프레임을 시청자(`viewer`) 화면(가운데)으로 전송
         - **데이터 규격**:
           ```json
           {
             "result_image": "data:image/jpeg;base64,.....(Base64 문자열)"
           }
           ```
         
      3. **`stream_status`**
         - **설명**: 현재 영상 처리 및 송출 상태를 알려줌
         - **데이터 규격**:
           ```json
           {
             "status": "streaming" // waiting, processing, streaming, stopped
           }
           ```
         
      4. **`stream_error`**
         - **설명**: 영상 가공 및 프레임 처리 과정에서 예외/오류가 발생했을 때 전달
         - **데이터 규격**:
           ```json
           {
             "code": "PROCESSING_FAILED",
             "message": "AI 프레임 가공 실패."
           }
           ```
    """
    return "이 페이지는 Swagger 문서 표시용 엔드포인트입니다."
