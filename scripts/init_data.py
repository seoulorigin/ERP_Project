import pymysql
from pymongo import MongoClient
import requests
import sys
import time

# [설정] 환경 변수 및 접속 정보
# 1. 서비스 URL
EMP_API_URL = "http://localhost:5001/employees"

# 2. MySQL (Employee Service DB)
MYSQL_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'password',  # 본인 환경에 맞게 수정
    'db': 'classdb',
    'charset': 'utf8mb4'
}

# 3. MongoDB (Request Service DB)
MONGO_URI = 'mongodb://localhost:27017/'
MONGO_DB = 'erp_db'
MONGO_COL = 'approvals'

# [기능 1] DB 초기화 (삭제)
def reset_databases():
    print("\n[Step 1] 데이터베이스 초기화 (Reset)...")
    
    # 1. MySQL 초기화
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        with conn.cursor() as cur:
            # TRUNCATE: 데이터 삭제 + ID 카운터 1로 초기화
            cur.execute("TRUNCATE TABLE employees")
            conn.commit()
        conn.close()
        print("MySQL 'employees' 테이블 초기화 완료 (ID 1부터 시작)")
    except Exception as e:
        print(f"MySQL 초기화 실패: {e}")
        return False

    # 2. MongoDB 초기화
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]
        db[MONGO_COL].drop()
        print(f"MongoDB '{MONGO_COL}' 컬렉션 삭제 완료")
    except Exception as e:
        print(f"MongoDB 초기화 실패: {e}")
        return False
        
    return True

# [기능 2] 필수 데이터 생성 (Seeding)
def seed_employees():
    print("\n🌱 [Step 2] 테스트용 직원 데이터 생성 (Seeding)...")
    
    # 생성할 직원 목록 (순서대로 ID 1, 2, 3 부여됨)
    users = [
        {"name": "이기안", "department": "개발팀", "position": "사원"},   # 예상 ID: 1
        {"name": "김결재", "department": "개발팀", "position": "팀장"},   # 예상 ID: 2
        {"name": "박이사", "department": "인사팀", "position": "이사"}    # 예상 ID: 3
    ]
    
    headers = {"Content-Type": "application/json"}
    
    for idx, user in enumerate(users, start=1):
        try:
            res = requests.post(EMP_API_URL, json=user, headers=headers)
            if res.status_code == 201:
                created_id = res.json()['id']
                print(f"직원 생성 성공: ID {created_id} ({user['name']} / {user['position']})")
                
                # ID 순서 검증
                if created_id != idx:
                    print(f" 경고: 예상 ID({idx})와 실제 ID({created_id})가 다릅니다.")
            else:
                print(f"생성 실패: {res.text}")
                return False
        except requests.exceptions.ConnectionError:
            print("[오류] Employee Service가 켜져 있지 않습니다!")
            return False
            
    return True

# 메인 실행
if __name__ == "__main__":
    print("========================================")
    print("ERP 테스트 데이터 셋업 도구")
    print("========================================")
    
    # 1. DB 밀기
    if reset_databases():
        print("reset DB Done")
        # 2. 데이터 채우기
        if seed_employees():
            print("seed employees Done")