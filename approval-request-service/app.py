from flask import Flask, request, jsonify
from flask_restx import Api, Resource
from pymongo import MongoClient
import grpc
from concurrent import futures
import threading
import sys
import os
import datetime
import requests

# proto 파일 경로 설정 (구조에 맞게 수정 필요)
sys.path.append(os.path.abspath("../proto")) 
import approval_pb2
import approval_pb2_grpc

app = Flask(__name__)
api = Api(app)

# MongoDB 연결
client = MongoClient('mongodb://localhost:27017/')
db = client['erp_db']
collection = db['approvals']

# --- [설정] 포트 관리 ---
PROCESSING_SERVICE_PORT = 50051  # Processing Service가 켜진 포트와 일치시켜야 함!
MY_GRPC_PORT = 50052             # 내(Request Service)가 수신할 포트
EMPLOYEE_SERVICE_URL = "http://localhost:5001"
NOTIFICATION_SERVICE_URL = "http://localhost:5004"

# --- [기능 1] gRPC Client: Processing Service로 요청 전달 ---
# 가이드 3.2.2 흐름 5번: gRPC를 통해 Approval Processing Service에 RequestApproval 호출 [cite: 49]
def send_to_processing(request_doc):
    print(f"[Client] Sending Request {request_doc['requestId']} to Processing Service...")
    
    try:
        # Processing Service 포트로 연결
        with grpc.insecure_channel(f'localhost:{PROCESSING_SERVICE_PORT}') as channel:
            stub = approval_pb2_grpc.ApprovalStub(channel)
            
            # Steps 변환 (Dict -> Proto Message)
            grpc_steps = []
            for s in request_doc['steps']:
                grpc_steps.append(approval_pb2.Step(
                    step=s['step'], 
                    approverId=s['approverId'], 
                    status=s['status']
                ))

            # gRPC 호출
            response = stub.RequestApproval(approval_pb2.ApprovalRequest(
                requestId=request_doc['requestId'],
                requesterId=request_doc['requesterId'],
                title=request_doc['title'],
                content=request_doc.get('content', ''),
                steps=grpc_steps
            ))
            print(f"[Client] Response: {response.status}")
            
    except Exception as e:
        print(f"[Client] Error sending to Processing Service: {e}")

# --- [기능 2] gRPC Server: 결과 수신 (ReturnApprovalResult) ---
class RequestServicer(approval_pb2_grpc.ApprovalServicer):
    # 가이드 3.2.4: Approval Processing Service로부터 ReturnApprovalResult 호출을 받음 [cite: 85]
    def ReturnApprovalResult(self, request, context):
        print(f"[Server] Result Received: ID {request.requestId}, Step {request.step}, Status {request.status}")
        
        # 1. MongoDB 업데이트 (해당 단계 상태 변경) [cite: 86]
        collection.update_one(
            {"requestId": request.requestId, "steps.step": request.step},
            {"$set": {"steps.$.status": request.status, "updatedAt": datetime.datetime.now()}}
        )
        
        # 최신 문서 다시 조회
        doc = collection.find_one({"requestId": request.requestId})
        if not doc:
            return approval_pb2.ApprovalResultResponse(status="error")
        
        # 2. 로직 분기: 반려(Rejected)인 경우 [cite: 86]
        if request.status == "rejected":
            collection.update_one(
                {"requestId": request.requestId}, 
                {"$set": {"finalStatus": "rejected", "updatedAt": datetime.datetime.now()}} # [cite: 87]
            )
            
            # Notification 호출 (가이드 3.2.4 - 2 & 3.4.2 반려 알림 구조) [cite: 88, 132-138]
            notify_payload = {
                "requestId": request.requestId,
                "result": "rejected",
                "rejectedBy": request.approverId, # 반려한 사람 ID
                "finalResult": "rejected"
            }
            try:
                # Notification Service는 targetId와 payload를 요구함
                requests.post(f"{NOTIFICATION_SERVICE_URL}/notify", json={
                    "targetId": doc['requesterId'],  # 알림 받을 사람 (기안자)
                    "payload": notify_payload        # 메시지 내용
                })
            except Exception as e:
                print(f"Notification Service unavailable: {e}")
            
        # 3. 로직 분기: 승인(Approved)인 경우 [cite: 89]
        elif request.status == "approved":
            # 다음 단계(pending) 확인 [cite: 90]
            next_step = None
            for s in doc['steps']:
                if s['status'] == 'pending':
                    next_step = s
                    break # 순차 진행이므로 첫 번째 pending만 찾으면 됨
            
            if next_step:
                print(f"[Server] Moving to next step: {next_step['step']}")
                # 다음 결재자에게 gRPC 전송 (재귀적 호출과 유사) [cite: 91]
                send_to_processing(doc)
            else:
                # 모든 단계 완료 [cite: 93]
                collection.update_one(
                    {"requestId": request.requestId}, 
                    {"$set": {"finalStatus": "approved", "updatedAt": datetime.datetime.now()}} # [cite: 94]
                )
                
                # Notification 호출 (가이드 3.2.4 - 3 & 3.4.2 승인 알림 구조) [cite: 95, 126-131]
                notify_payload = {
                    "requestId": request.requestId,
                    "result": "approved",
                    "finalResult": "approved"
                }
                try:
                    requests.post(f"{NOTIFICATION_SERVICE_URL}/notify", json={
                        "targetId": doc['requesterId'], # 알림 받을 사람 (기안자)
                        "payload": notify_payload       # 메시지 내용
                    })
                except Exception as e:
                    print(f"Notification Service unavailable: {e}")

        return approval_pb2.ApprovalResultResponse(status="success")

# -- Helper: User 존재 확인 --
def check_user_exists(id):
    try:
        res = requests.get(f"{EMPLOYEE_SERVICE_URL}/employees/{id}")
        return res.status_code == 200
    except:
        return False # Employee Service가 꺼져있으면 없는 것으로 처리

# --- [Helper] MongoDB 문서 JSON 직렬화 ---
def serialize_doc(doc):
    if not doc:
        return None
    # _id는 JSON 변환 시 오류가 나므로 제거하거나 문자열로 변환
    if '_id' in doc:
        del doc['_id']
    # datetime 객체를 ISO 포맷 문자열로 변환
    if 'createdAt' in doc and isinstance(doc['createdAt'], datetime.datetime):
        doc['createdAt'] = doc['createdAt'].isoformat()
    if 'updatedAt' in doc and isinstance(doc['updatedAt'], datetime.datetime):
        doc['updatedAt'] = doc['updatedAt'].isoformat()
    return doc

@api.route('/approvals')
class Approval(Resource):
    def post(self):
        data = request.json
        requester_id = data.get('requesterId')
        
        # 1. Employee Service 검증 [cite: 49]
        if not check_user_exists(requester_id):
            return {"message": f"Requester {requester_id} does not exist."}, 400

        cnt = 1
        steps = data.get('steps')
        for step in steps:
            # 2. Steps 검증 [cite: 49]
            if not step['step'] == cnt:
                return {"message": "Step Order Error. Steps must be sequential starting from 1."}, 400
            cnt += 1
            if not check_user_exists(step['approverId']):
                return {"message": f"Approver {step['approverId']} does not exist."}, 400
            
            # 3. 초기 상태 pending 추가 [cite: 49]
            step['status'] = "pending"

        req_id = int(datetime.datetime.now().timestamp())

        doc = {
            "requestId": req_id,
            "requesterId": requester_id,
            "title": data['title'],
            "content": data.get('content', ''),
            "steps": steps, 
            "finalStatus": "in_progress",
            "createdAt": datetime.datetime.now()
        }

        # 4. MongoDB INSERT [cite: 49]
        collection.insert_one(doc) # insert_one을 명시적으로 호출하는 것이 좋습니다.
        print(f"Created Approval Request: {doc}")

        # 5. gRPC를 통해 Approval Processing Service 호출 [cite: 49]
        # ★ 수정됨: client_grpc(X) -> send_to_processing(O)
        send_to_processing(doc)
        
        return {"requestId": req_id}, 201

    def get(self):
        # created_at 기준 내림차순 정렬 (최신순)
        cursor = collection.find({}).sort("createdAt", -1)
        results = [serialize_doc(doc) for doc in cursor]
        return results, 200

@api.route('/approvals/<int:request_id>')
class ApprovalDetail(Resource):
    # [cite_start][GET] 결재 요청 상세 조회 [cite: 49] (이미지 표 두 번째 행)
    def get(self, request_id):
        """특정 requestId에 해당하는 Document 반환"""
        doc = collection.find_one({"requestId": request_id})
        
        if not doc:
            return {"message": f"Request {request_id} not found."}, 404
            
        return serialize_doc(doc), 200

    # [cite_start][DELETE] 결재 요청 삭제 [cite: 49] (이미지 표 세 번째 행)
    def delete(self, request_id):
        """기능 없음 (삭제 불가 메시지 반환)"""
        # 가이드: "기능 없음. 결재자가 Rejected해야만 처리 종료 가능."
        return {
            "message": "Deletion is not allowed. The process ends only upon rejection."
        }, 405  # 405 Method Not Allowed 또는 400 Bad Request

# gRPC 서버 실행 함수
def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    approval_pb2_grpc.add_ApprovalServicer_to_server(RequestServicer(), server)
    server.add_insecure_port(f'[::]:{MY_GRPC_PORT}')
    print(f"Approval Request Service (gRPC) started on port {MY_GRPC_PORT}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    # 1. gRPC 서버 스레드 실행
    t = threading.Thread(target=serve_grpc)
    t.daemon = True # 메인 프로세스 종료 시 함께 종료되도록 설정
    t.start()
    
    # 2. Flask 웹 서버 실행
    # use_reloader=False 필수 (스레드 중복 실행 방지)
    app.run(port=5002, debug=True, use_reloader=False)