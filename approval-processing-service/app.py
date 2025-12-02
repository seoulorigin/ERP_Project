from flask import Flask, request, jsonify
import grpc
from concurrent import futures
import threading
import sys
import os

# Proto 파일 경로 설정
sys.path.append(os.path.abspath("../proto"))
import approval_pb2
import approval_pb2_grpc

app = Flask(__name__)

# In-Memory 저장소
# 구조: { "approverId_String": [ {request_data}, ... ] }
approval_queue = {}

# --- gRPC Server 구현 (RequestApproval 처리) ---
class ApprovalServicer(approval_pb2_grpc.ApprovalServicer):
    def RequestApproval(self, request, context):
        print(f"[gRPC] Received Approval Request: ID {request.requestId}")
        
        # steps 중 첫 번째 pending 상태인 approver 찾기 [cite: 117]
        target_approver = None
        for step in request.steps:
            if step.status == "pending":
                target_approver = str(step.approverId)
                break
        
        if target_approver:
            if target_approver not in approval_queue:
                approval_queue[target_approver] = []
            
            # gRPC 메시지를 dict로 변환하여 저장 (단순화)
            req_data = {
                "requestId": request.requestId,
                "title": request.title,
                "steps": [{"step": s.step, "approverId": s.approverId, "status": s.status} for s in request.steps]
            }
            approval_queue[target_approver].append(req_data)

        return approval_pb2.ApprovalResponse(status="received")

# --- REST API 구현 (결재자가 승인/반려 처리) ---
@app.route('/process/<approver_id>', methods=['GET'])
def get_queue(approver_id):
    return jsonify(approval_queue.get(approver_id, []))

@app.route('/process/<approver_id>/<int:request_id>', methods=['POST'])
def process_approval(approver_id, request_id):
    data = request.json # {"status": "approved"}
    status = data.get("status")
    
    # 1. 대기열에서 제거 로직 (생략 가능, 여기선 찾아서 처리)
    queue = approval_queue.get(approver_id, [])
    
    # 2. Request Service로 결과 전송 (gRPC Client) [cite: 120]
    # Request Service의 gRPC 포트는 50052로 가정
    with grpc.insecure_channel('localhost:50052') as channel:
        stub = approval_pb2_grpc.ApprovalStub(channel)
        # 현재 단계 번호 찾기 (단순화: 1로 가정하거나 저장된 데이터 사용)
        step_num = 1 
        for req in queue:
            if req['requestId'] == request_id:
                # 해당 요청의 현재 스텝 찾기 로직 필요
                pass 

        stub.ReturnApprovalResult(approval_pb2.ApprovalResultRequest(
            requestId=request_id,
            step=step_num, # 실제 로직에선 저장된 step 번호 사용
            approverId=int(approver_id),
            status=status
        ))
        
    return jsonify({"message": "Processed"}), 200

def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    approval_pb2_grpc.add_ApprovalServicer_to_server(ApprovalServicer(), server)
    server.add_insecure_port('[::]:50053') # Processing Service gRPC Port
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    # gRPC 서버를 별도 스레드로 실행
    t = threading.Thread(target=serve_grpc)
    t.start()
    app.run(port=5003, debug=True)