import requests, json
import time

EMP_URL = "http://localhost:5001"

def JSON(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

# 직원 등록
def register():
    headers = {'Content-Type': 'application/json', 'charset': 'UTF-8', 'Accept': '*/*'}
    body = {'key': 'value'}

    print("[직원 등록]")
    
    employee = {
        "name": "Kim",
        "department": "Sales",
        "position": "Manager"
    }

    res = requests.post(f"{EMP_URL}/employees", json=employee)
    if res.status_code == 201:
        print(res.json())
    else :
        print("Error")

if __name__ == "__main__":
    register()