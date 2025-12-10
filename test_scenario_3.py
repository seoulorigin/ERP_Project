import requests, json
import time

EMP_URL = "http://localhost:5001/employees"
APPROVAL_URL = "http://localhost:5002/approvals"
PROCESSING_URL = "http://localhost:5003/process"

employee = {
    "name": "Kim",
    "department": "Sales",
    "position": "Manager"
}

payload = {
    "department": "Sales",
    "position": "Manager"
}

emp_id = 2

update_data = {
    "department": "Finance",
    "position": "Director"
}

approval_data = {
    "requesterId": 1,
    "title": "휴가 신청서",
    "content": "개인 사정으로 인한 연차 신청",
    "steps": [
        {"step": 1, "approverId": 7}, # 1차 결재자
        {"step": 2, "approverId": 8}  # 2차 결재자
    ]
}

# 직원 등록
def register():
    print("[직원 등록]")

    res = requests.post(EMP_URL, json=employee)
    if res.status_code == 201:
        print(res.json())
    else :
        print("Error")

# 직원 찾기
def research():
    print("[직원 찾기]")
    res = requests.get(EMP_URL, params=payload)
    if res.status_code == 200:
        print(res.json())
    else:
        print("Error")

# 직원 상세 조회
def detail():
    print("[직원 상세 조회]")
    res = requests.get(EMP_URL + f"/{emp_id}")
    if res.status_code == 200:
        print(res.json())
    else:
        print("Error")

def adjust():
    print("[직원 수정]")
    res = requests.put(EMP_URL + f"/{emp_id}", json=update_data)
    if res.status_code == 200:
        print(res.json())
    else:
        print("Error")

def delete():
    print("[직원 삭제]")
    res = requests.delete(EMP_URL + f"/{emp_id}")
    if res.status_code == 204:
        print("Success")
    else:
        print("Error")

def approval_post():
    print("\n[1. 결재 요청 생성] Request Service -> DB 저장 -> Processing Service 전송")
    res = requests.post(APPROVAL_URL, json=approval_data)
    
    if res.status_code == 201:
        result = res.json()
        print(f"ㄴ 성공: {result}")
        return result['requestId'] # 다음 단계 테스트를 위해 ID 반환
    else :
        print(f"ㄴ 실패: {res.text}")
        return None

def check_queue(approver_id):
    print(f"\n[대기열 조회] 결재자 ID: {approver_id}")
    try:
        res = requests.get(f"{PROCESSING_URL}/{approver_id}")
        if res.status_code == 200:
            queue = res.json()
            print(f"ㄴ 대기 목록 개수: {len(queue)}")
            for item in queue:
                print(f"   - RequestID: {item['requestId']}, Title: {item['title']}, Step: {item.get('currentStep')}")
            return queue
        else:
            print(f"ㄴ 조회 실패: {res.status_code}")
            return []
    except Exception as e:
        print(f"ㄴ 연결 오류: {e}")
        return []

def process_approval(approver_id, request_id, status="approved"):
    print(f"\n[결재 처리] 결재자 {approver_id}가 Request {request_id}를 '{status}' 처리함")
    payload = {"status": status}
    
    try:
        # 가이드 URI: /process/{approverId}/{requestId} 
        res = requests.post(f"{PROCESSING_URL}/{approver_id}/{request_id}", json=payload)
        
        if res.status_code == 200:
            print(f"ㄴ 처리 성공: {res.json()}")
        else:
            print(f"ㄴ 처리 실패: {res.status_code} {res.text}")
    except Exception as e:
        print(f"ㄴ 오류 발생: {e}")

if __name__ == "__main__":
    #register()
    #research()
    #detail()
    #adjust()
    #delete()

    # -- 테스트 --
    req_id = approval_post()
    time.sleep(1)

    # 7번 확인
    queue = check_queue(7)

    if any(q['requestId'] == req_id for q in queue):
        process_approval(7, req_id, "approved")
            
        print("\n... [시스템 내부] Request Service가 결과 수신 후 다음 단계(8번)로 전달 중 ...")
        time.sleep(2) # gRPC 통신 및 DB 업데이트 대기
            
        # 4. 2차 결재자(8번) 대기열 확인 (자동으로 넘어왔는지 검증)
        queue_2nd = check_queue(8)
            
        # 5. 2차 승인 처리 (최종 완료)
        if any(q['requestId'] == req_id for q in queue_2nd):
            process_approval(8, req_id, "approved")
            print("\n[최종 완료] 모든 결재가 승인되었습니다.")
        else:
                print(f"\n[오류] 2차 결재자(8번)에게 결재가 넘어오지 않았습니다.")
    else:
        print(f"\n[오류] 1차 결재자(7번) 대기열에 요청이 없습니다.")