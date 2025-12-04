import requests, json
import time

EMP_URL = "http://localhost:5001/employees"

employee = {
    "name": "Kim",
    "department": "Sales",
    "position": "Manager"
}

payload = {
    "department": "Sales",
    "position": "Manager"
}

emp_id = 1

update_data = {
    "department": "Finance",
    "position": "Director"
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


if __name__ == "__main__":
    #register()
    #research()
    #detail()
    adjust()