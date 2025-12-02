from flask import Flask, request, jsonify
from pymongo import MongoClient
import grpc
from concurrent import futures
import threading
import sys
import os
import datetime
import requests

sys.path.append(os.path.abspath("../proto"))
import approval_pb2
import approval_pb2_grpc

app = Flask(__name__)
client = MongoClient('mongodb://localhost:27017/')
db = client['erp_db']
collection = db['approvals']

# --- gRPC Client Helper ---
def send_to_processing(request_doc):
    # Processing Service(50053)로 요청 전달
    with grpc.insecure_channel('localhost:50053') as channel:
        stub = approval_pb2_grpc.ApprovalStub(channel)
        
        # Steps 변환
        grpc_steps = []
        for s in request_doc['steps']:
            grpc_steps.append(approval_pb2.Step(
                step=s['step'], approverId=s['approverId'], status=s['status']
            ))

        stub.RequestApproval(approval_pb2.ApprovalRequest(
            requestId=request_doc['requestId'],
            requesterId=request_doc['requesterId'],
            title=request_doc['title'],
            content=request_doc['content'],
            steps=grpc_steps
        ))

# --- gRPC Server 구현 (ReturnApprovalResult 수신) ---
class RequestServicer(approval_pb2_grpc.ApprovalServicer):
    def ReturnApprovalResult(self, request, context):
        print(f"[gRPC] Result Received: ID {request.requestId}, Status {request.status}")
        
        # 1. MongoDB 업데이트 [cite: 86]
        collection.update_one(
            {"requestId": request.requestId, "steps.step": request.step},
            {"$set": {"steps.$.status": request.status, "updatedAt": datetime.datetime.now()}}
        )
        
        doc = collection.find_one({"requestId": request.requestId})
        
        # 2. 로직 분기 [cite: 87-95]
        if request.status == "rejected":
            collection.update_one({"requestId": request.requestId}, {"$set": {"finalStatus": "rejected"}})
            # Notification 호출 (HTTP로 가정)
            requests.post("http://localhost:5004/notify", json={"requestId": request.requestId, "msg": "Rejected"})
            
        elif request.status == "approved":
            # 다음 단계 확인
            next_step = None
            all_done = True
            for s in doc['steps']:
                if s['status'] == 'pending':
                    next_step = s
                    all_done = False
                    break
            
            if next_step:
                # 다음 결재자에게 gRPC 전송 [cite: 91]
                send_to_processing(doc)
            else:
                # 모든 결재 완료
                collection.update_one({"requestId": request.requestId}, {"$set": {"finalStatus": "approved"}})
                requests.post("http://localhost:5004/notify", json={"requestId": request.requestId, "msg": "Approved"})

        return approval_pb2.ApprovalResultResponse(status="success")

# --- REST API ---
@app.route('/approvals', methods=['POST'])
def create_approval():
    data = request.json
    # ID 생성 로직 단순화 (Auto Increment 대신 timestamp 등 사용 권장)
    req_id = int(datetime.datetime.now().timestamp())
    
    # steps 초기화 및 저장
    steps = data['steps']
    for s in steps:
        s['status'] = 'pending'
        
    doc = {
        "requestId": req_id,
        "requesterId": data['requesterId'],
        "title": data['title'],
        "content": data['content'],
        "steps": steps,
        "finalStatus": "in_progress",
        "createdAt": datetime.datetime.now()
    }
    collection.insert_one(doc)
    
    # gRPC 호출
    send_to_processing(doc)
    
    return jsonify({"requestId": req_id}), 201

def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # 주의: Request Service는 ReturnApprovalResult만 처리하면 되지만,
    # Proto 정의상 전체 서비스를 등록해야 하므로 비어있는 메서드는 패스되거나 에러를 뱉을 수 있음.
    # 여기서는 편의상 동일한 Servicer 클래스 구조 사용.
    approval_pb2_grpc.add_ApprovalServicer_to_server(RequestServicer(), server)
    server.add_insecure_port('[::]:50052') # Request Service gRPC Port
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    t = threading.Thread(target=serve_grpc)
    t.start()
    app.run(port=5002, debug=True)