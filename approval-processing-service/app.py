from flask import Flask, request, jsonify
import grpc
from concurrent import futures
import threading
import sys
import os

# Proto 파일 경로 설정 (환경에 맞게 수정)
sys.path.append(os.path.abspath("../proto"))
import approval_pb2
import approval_pb2_grpc

app = Flask(__name__)

# --- [설정] 포트 관리 ---
# 내(Processing Service)가 실행될 gRPC 포트
MY_GRPC_PORT = 50051 
# 결과 회신을 보낼 Request Service의 gRPC 포트
REQUEST_SERVICE_GRPC_PORT = 50052 

# In-Memory 저장소
# 구조: { "approverId_String": [ {request_data}, ... ] }
approval_queue = {}

# --- [기능 1] gRPC Server: RequestApproval 처리 ---
class ApprovalServicer(approval_pb2_grpc.ApprovalServicer):
    # 가이드 3.3.2: RequestApproval 호출 수신 시 처리 흐름
    def RequestApproval(self, request, context):
        print(f"[gRPC Server] Received Approval Request: ID {request.requestId}")
        
        # 1. steps 중 첫 번째 pending 상태인 approver 찾기 [cite: 117]
        target_approver = None
        current_step_num = 0
        
        # 데이터 저장을 위해 gRPC 객체를 dict 리스트로 변환
        steps_list = []
        for step in request.steps:
            steps_list.append({
                "step": step.step,
                "approverId": step.approverId,
                "status": step.status
            })
            # 아직 타겟을 못 찾았고, 현재 스텝이 pending이면 타겟으로 설정
            if target_approver is None and step.status == "pending":
                target_approver = str(step.approverId)
                current_step_num = step.step
        
        # 2. 해당 approverId를 키로 하는 인메모리 대기 리스트에 저장 [cite: 118]
        if target_approver:
            if target_approver not in approval_queue:
                approval_queue[target_approver] = []
            
            # 가이드 3.3.1 예시에 맞춘 상세 데이터 저장
            req_data = {
                "requestId": request.requestId,
                "requesterId": request.requesterId,
                "title": request.title,
                "content": request.content, # 내용 포함
                "steps": steps_list,
                "currentStep": current_step_num # 처리를 위해 편의상 저장
            }
            approval_queue[target_approver].append(req_data)
            print(f"[gRPC Server] Added to Approver {target_approver}'s queue (Step {current_step_num})")

        # 3. 응답 반환 [cite: 118]
        return approval_pb2.ApprovalResponse(status="received")
    
    # (필수 구현) Interface 충족을 위해 빈 메서드 정의
    def ReturnApprovalResult(self, request, context):
        return approval_pb2.ApprovalResultResponse(status="ok")

# --- [기능 2] REST API: 결재 처리 (승인/반려) ---
@app.route('/process/<approver_id>', methods=['GET'])
def get_queue(approver_id):
    # 가이드 3.3.3: 대기 목록 조회
    return jsonify(approval_queue.get(approver_id, []))

@app.route('/process/<approver_id>/<int:request_id>', methods=['POST'])
def process_approval(approver_id, request_id):
    # 가이드 3.3.3: 승인 또는 반려 처리
    # Request: {"status": "approved"} or {"status": "rejected"}
    data = request.json 
    status = data.get("status")
    
    if approver_id not in approval_queue:
        return jsonify({"message": "No queue for this approver"}), 404

    queue = approval_queue[approver_id]
    target_req = None
    
    # 1. 대기열에서 해당 요청 찾기
    for req in queue:
        if req['requestId'] == request_id:
            target_req = req
            break
    
    if not target_req:
        return jsonify({"message": "Request ID not found in queue"}), 404

    # 2. 대기열에서 제거 (처리 완료되었으므로) 
    queue.remove(target_req)
    print(f"[API] Request {request_id} processed as {status} by {approver_id}. Removed from queue.")

    # 3. Request Service로 결과 전송 (gRPC Client) 
    try:
        with grpc.insecure_channel(f'localhost:{REQUEST_SERVICE_GRPC_PORT}') as channel:
            stub = approval_pb2_grpc.ApprovalStub(channel)
            
            print(f"[gRPC Client] Sending result to Request Service (Port {REQUEST_SERVICE_GRPC_PORT})...")
            
            stub.ReturnApprovalResult(approval_pb2.ApprovalResultRequest(
                requestId=request_id,
                step=target_req['currentStep'], # 저장해둔 단계 번호 사용
                approverId=int(approver_id),
                status=status
            ))
    except Exception as e:
        print(f"[Error] Failed to report result via gRPC: {e}")
        # 실패 시 큐에 복구하는 로직이 필요할 수 있으나, 여기선 생략
        return jsonify({"message": "Processed locally but failed to notify Request Service"}), 500
        
    return jsonify({"message": "Processed successfully"}), 200

# gRPC 서버 실행 함수
def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    approval_pb2_grpc.add_ApprovalServicer_to_server(ApprovalServicer(), server)
    server.add_insecure_port(f'[::]:{MY_GRPC_PORT}')
    print(f"Approval Processing Service (gRPC) started on port {MY_GRPC_PORT}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    # 1. gRPC 서버 스레드 실행
    t = threading.Thread(target=serve_grpc)
    t.daemon = True
    t.start()
    
    # 2. Flask 웹 서버 실행
    # Request Service(5002)와 충돌 방지를 위해 5003 포트 사용
    # use_reloader=False 필수
    app.run(port=5003, debug=True, use_reloader=False)