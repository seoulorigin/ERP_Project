from flask import Flask, request, jsonify
import pymysql

app = Flask(__name__)

# DB 설정 (init_mysql.sql 참고)
def get_db_connection():
    return pymysql.connect(
        host='localhost', user='root', password='password',
        db='classdb', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/employees', methods=['POST'])
def create_employee():
    data = request.json
    conn = get_db_connection()
    with conn.cursor() as cur:
        sql = "INSERT INTO employees (name, department, position) VALUES (%s, %s, %s)"
        cur.execute(sql, (data['name'], data['department'], data['position']))
        conn.commit()
        new_id = cur.lastrowid
    conn.close()
    return jsonify({"id": new_id}), 201

@app.route('/employees', methods=['GET'])
def get_employees():
    # 쿼리 파라미터 처리 생략 (예시 단순화)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM employees")
        result = cur.fetchall()
    conn.close()
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=5001, debug=True)