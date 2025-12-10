import requests
import time
import threading
import asyncio
import websockets
import json
import sys

# --- [설정] 서비스 URL 및 포트 ---
# 파일 분석 결과에 따른 포트 설정
EMP_URL = "http://localhost:5001/employees"
REQ_URL = "http://localhost:5002/approvals"
PROC_URL = "http://localhost:5003/process"
NOTI_WS = "ws://localhost:8081/ws"  # Notification Service의 WS 포트 

# --- [전역 변수] 테스트 결과 저장용 ---
ws_messages = []
is_ws_connected = False

# --- 1. WebSocket 리스너 (별도 스레드) ---
async def websocket_listener(employee_id):
    global is_ws_connected
    uri = f"{NOTI_WS}?id={employee_id}"
    print(f"   [WS] Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            is_ws_connected = True
            print(f"   [WS] Connected! (Employee {employee_id})")
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    print(f"\n⚡ [실시간 알림 수신] {json.dumps(data, indent=2, ensure_ascii=False)}\n")
                    ws_messages.append(data)
                except websockets.exceptions.ConnectionClosed:
                    break
    except Exception as e:
        print(f"   [WS] Connection Failed: {e}")

def start_ws_client(employee_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(websocket_listener(employee_id))

# --- 2. REST API 헬퍼 함수 ---
def create_employee(name, dept, pos):
    res = requests.post(EMP_URL, json={"name": name, "department": dept, "position": pos})
    if res.status_code == 201:
        return res.json()['id']
    return None

def create_approval_request(requester_id, title, steps):
    payload = {
        "requesterId": requester_id,
        "title": title,
        "content": "자동화 테스트 내용입니다.",
        "steps": steps
    }
    res = requests.post(REQ_URL, json=payload)
    if res.status_code == 201:
        return res.json()['requestId']
    else:
        print(f"   [Error] Request Creation Failed: {res.text}")
        return None

def process_approval(approver_id, req_id, status):
    # 대기열 확인
    res = requests.get(f"{PROC_URL}/{approver_id}")
    queue = res.json()
    
    target = next((item for item in queue if item['requestId'] == req_id), None)
    if not target:
        print(f"   [Fail] Request {req_id} not found in Approver {approver_id}'s queue.")
        return False

    # 처리 요청
    res = requests.post(f"{PROC_URL}/{approver_id}/{req_id}", json={"status": status})
    if res.status_code == 200:
        print(f"   [Success] Approver {approver_id} processed as '{status}'")
        return True
    return False

# --- 3. 메인 테스트 로직 ---
def run_test():
    print("==================================================")
    print("ERP 프로젝트 최종 통합 테스트 시나리오")
    print("==================================================")

    # 1. 직원 데이터 준비 (기안자, 결재자1, 결재자2)
    print("\n[Step 1] 직원 데이터 생성")
    user_requester = 1 # 편의상 ID 고정 (DB 초기화 상태 가정)
    user_approver1 = 2
    user_approver2 = 3
    
    # 실제로는 DB에 없으면 생성하는 로직이 좋으나, 테스트 편의를 위해 1,2,3이 있다고 가정하거나 생성 시도
    # (Employee Service가 켜져 있어야 함)
    
    # 2. WebSocket 연결 (기안자 ID: 1)
    print("\n[Step 2] WebSocket 연결 (기안자 알림 수신 대기)")
    t = threading.Thread(target=start_ws_client, args=(user_requester,), daemon=True)
    t.start()
    time.sleep(2) # 연결 대기

    # --- 시나리오 A: 정상 승인 완료 (2단계) ---
    print("\n" + "-"*50)
    print("[Scenario A] 2단계 결재 '최종 승인' 테스트")
    print("-" * 50)
    
    req_id_a = create_approval_request(
        user_requester, 
        "구매 요청서 (Scenario A)", 
        [{"step": 1, "approverId": user_approver1}, {"step": 2, "approverId": user_approver2}]
    )
    print(f"   -> 결재 요청 생성됨 (ID: {req_id_a})")
    time.sleep(1)

    # 1차 승인
    print(f"   -> 1차 결재자({user_approver1}) 승인 시도...")
    process_approval(user_approver1, req_id_a, "approved")
    time.sleep(1) # gRPC 전송 대기

    # 2차 승인
    print(f"   -> 2차 결재자({user_approver2}) 승인 시도 (자동 전달 확인)...")
    process_approval(user_approver2, req_id_a, "approved")
    
    # 결과 확인 (WebSocket)
    print("   -> 알림 수신 대기 중 (3초)...")
    time.sleep(3)
    
    # --- 시나리오 B: 중간 반려 (Rejection) ---
    print("\n" + "-"*50)
    print("[Scenario B] 결재 '반려' 테스트")
    print("-" * 50)

    req_id_b = create_approval_request(
        user_requester, 
        "휴가 신청서 (Scenario B)", 
        [{"step": 1, "approverId": user_approver1}, {"step": 2, "approverId": user_approver2}]
    )
    print(f"   -> 결재 요청 생성됨 (ID: {req_id_b})")
    time.sleep(1)

    # 1차 반려
    print(f"   -> 1차 결재자({user_approver1}) 반려 시도...")
    process_approval(user_approver1, req_id_b, "rejected")
    
    print("   -> 알림 수신 대기 중 (3초)...")
    time.sleep(3)

    # --- 최종 검증 ---
    print("\n" + "="*50)
    print("테스트 결과 요약")
    print("=" * 50)
    
    approved_noti = next((msg for msg in ws_messages if msg.get('requestId') == req_id_a and msg.get('finalResult') == 'approved'), None)
    rejected_noti = next((msg for msg in ws_messages if msg.get('requestId') == req_id_b and msg.get('finalResult') == 'rejected'), None)

    if approved_noti:
        print(f"✅ Scenario A 성공: 최종 승인 알림 수신됨 ({approved_noti})")
    else:
        print(f"❌ Scenario A 실패: 최종 승인 알림 미수신")

    if rejected_noti:
        print(f"✅ Scenario B 성공: 반려 알림 수신됨 ({rejected_noti})")
    else:
        print(f"❌ Scenario B 실패: 반려 알림 미수신")

if __name__ == "__main__":
    run_test()