import requests
import time
import threading
import asyncio
import websockets
import json
import sys

# 서비스별 접속 주소 설정
# (로컬 환경 기준, 포트번호는 작성해주신 코드와 일치해야 합니다)
EMP_URL = "http://localhost:5001"
REQ_URL = "http://localhost:5002"
PROC_URL = "http://localhost:5003"
NOTI_WS = "ws://localhost:8085"  # 요청하신 8085 포트 반영

# 1. [Notification] WebSocket 리스너 (별도 스레드에서 실행)
async def listen_ws():
    # Requester(직원ID 1번)으로 접속한다고 가정
    uri = f"{NOTI_WS}/ws?id=1"
    print(f"[WS] Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("[WS] Connected! Waiting for notifications...")
            while True:
                # 메시지가 오면 수신해서 출력
                msg = await websocket.recv()
                print(f"\n\n[🔔 알림 수신] {msg}\n")
    except Exception as e:
        print(f"[WS] Connection Error or Closed: {e}")

def start_ws_client():
    # 비동기 함수 실행을 위한 래퍼
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_ws())

# 2. 메인 테스트 시나리오
def run_test():
    print("=== ERP 통합 테스트 시작 ===")

    # (1) 웹소켓 리스너 스레드 시작
    t = threading.Thread(target=start_ws_client, daemon=True)
    t.start()
    time.sleep(2) # 연결될 때까지 잠시 대기

    try:
        # (2) 직원 목록 확인
        print("\n--- [Step 1] Employee Service: 직원 목록 조회 ---")
        res = requests.get(f"{EMP_URL}/employees")
        if res.status_code == 200:
            print(f"Result: {res.json()}")
        else:
            print("Error: 직원 서비스를 확인하세요.")
            return

        # (3) 결재 요청 생성 (Requester -> Approver)
        print("\n--- [Step 2] Request Service: 결재 요청 생성 ---")
        # 시나리오: 1번 직원이 2번 직원에게 결재 요청
        approval_data = {
            "requesterId": 1,
            "title": "테스트 결재 요청",
            "content": "테스트 내용입니다.",
            "steps": [
                {"step": 1, "approverId": 2}
            ]
        }
        res = requests.post(f"{REQ_URL}/approvals", json=approval_data)
        if res.status_code == 201:
            req_id = res.json()['requestId']
            print(f"Success! Created Request ID: {req_id}")
        else:
            print(f"Error: {res.text}")
            return
        
        time.sleep(1) # 데이터 전달 대기

        # (4) 결재자 대기열 확인
        print(f"\n--- [Step 3] Processing Service: 결재자(ID:2) 대기열 확인 ---")
        res = requests.get(f"{PROC_URL}/process/2")
        queue = res.json()
        print(f"Current Queue for Approver 2: {queue}")

        if len(queue) == 0:
            print("대기열이 비어있습니다. gRPC 통신을 확인하세요.")
            return

        # (5) 결재 승인 처리
        print(f"\n--- [Step 4] Processing Service: 승인 처리 (Approved) ---")
        # 대기열에 있는 해당 요청 승인
        target_req_id = queue[0]['requestId'] # 위에서 생성된 ID 사용
        
        process_data = {"status": "approved"}
        res = requests.post(f"{PROC_URL}/process/2/{target_req_id}", json=process_data)
        
        if res.status_code == 200:
            print(f"Processing Result: {res.json()}")
        else:
            print(f"Error: {res.text}")

        print("\n--- [Step 5] 최종 알림 수신 대기 (3초) ---")
        time.sleep(3)
        print("\n=== 테스트 종료 ===")

    except Exception as e:
        print(f"\n[Error] 테스트 중 예외 발생: {e}")
        print("모든 서비스(4개)가 실행 중인지 확인해주세요.")

if __name__ == "__main__":
    run_test()