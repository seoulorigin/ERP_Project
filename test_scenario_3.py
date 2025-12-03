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


if __name__ == "__main__":
    #register()
    research()