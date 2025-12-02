import requests
import time
import threading
import asyncio
import websockets
import json
import sys

# --- 설정 ---
EMP_URL = "http://localhost:5001"
REQ_URL = "http://localhost:5002"
PROC_URL = "http://localhost:5003"
NOTI_WS = "ws://localhost:8085"

# --- 출력 헬퍼 함수 ---
def print_header(title):
    print(f"\n{'='*50}")
    print(f"🚀 {title}")
    print(f"{'='*50}")

def print_sub(title):
    print(f"\n👉 {title}")

def print_json(label, data):
    print(f"{label}:")
    # JSON을 들여쓰기하여 예쁘게 출력
    print(json.dumps(data, indent=2, ensure_ascii=False))

def print_success(msg):
    print(f"✅ {msg}")

def print_error(msg):
    print(f"❌ {msg}")

# --- WebSocket 리스너 ---
async def listen_ws():
    uri = f"{NOTI_WS}/ws?id=1"
    try:
        async with websockets.connect(uri) as websocket:
            print("   (WS 연결 성공! 알림 대기 중...)")
            while True:
                msg = await websocket.recv()
                print(f"\n\n{'*'*50}")
                print(f"🔔 [실시간 알림 수신]")
                try:
                    data = json.loads(msg)
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                except:
                    print(msg)
                print(f"{'*'*50}\n")
    except Exception as e:
        print(f"   (WS 연결 실패: {e})")

def start_ws_client():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(listen_ws())

# --- 메인 테스트 시나리오 ---
def run_test():
    print_header("ERP 통합 테스트 시작")

    # 1. WebSocket 연결
    print_sub("WebSocket 연결 시도 (Requester ID: 1)")
    t = threading.Thread(target=start_ws_client, daemon=True)
    t.start()
    time.sleep(2) 

    try:
        # 2. 직원 목록 확인
        print_header("Step 1: 직원 목록 조회 (Employee Service)")
        res = requests.get(f"{EMP_URL}/employees")
        if res.status_code == 200:
            print_json("📋 직원 목록", res.json())
        else:
            print_error(f"실패: {res.text}")
            return

        # 3. 결재 요청 생성
        print_header("Step 2: 결재 요청 생성 (Request Service)")
        approval_data = {
            "requesterId": 1,
            "title": "맥북 프로 구매 요청",
            "content": "개발 장비가 필요합니다.",
            "steps": [
                {"step": 1, "approverId": 2}
            ]
        }
        print_json("📤 요청 데이터", approval_data)
        
        res = requests.post(f"{REQ_URL}/approvals", json=approval_data)
        if res.status_code == 201:
            req_id = res.json()['requestId']
            print_success(f"결재 요청 생성 완료! (ID: {req_id})")
        else:
            print_error(f"실패: {res.text}")
            return
        
        time.sleep(1)

        # 4. 결재자 대기열 확인
        print_header("Step 3: 결재자 대기열 확인 (Processing Service)")
        print_sub("결재자(ID: 2)의 대기열 조회 중...")
        
        res = requests.get(f"{PROC_URL}/process/2")
        queue = res.json()
        
        if len(queue) > 0:
            print_json("📥 수신된 결재 요청", queue)
        else:
            print_error("대기열이 비어있습니다! gRPC 통신을 확인하세요.")
            return

        # 5. 승인 처리
        print_header("Step 4: 결재 승인 처리 (Processing Service)")
        target_req_id = queue[0]['requestId']
        
        print_sub(f"요청 ID {target_req_id} 승인 시도...")
        process_data = {"status": "approved"}
        
        res = requests.post(f"{PROC_URL}/process/2/{target_req_id}", json=process_data)
        
        if res.status_code == 200:
            print_success("승인 처리 완료!")
            print_json("결과", res.json())
        else:
            print_error(f"실패: {res.text}")

        # 6. 알림 대기
        print_header("Step 5: 최종 알림 수신 대기")
        print("⏳ 3초간 대기합니다...")
        time.sleep(3)
        print_header("테스트 종료")

    except Exception as e:
        print_error(f"테스트 중 예외 발생: {e}")
        print("💡 팁: 모든 서비스(4개)가 실행 중인지 확인해주세요.")

if __name__ == "__main__":
    run_test()