from flask import Flask, request, jsonify
from flask_restx import Api, Resource
import pymysql

app = Flask(__name__)
api = Api(app)

def get_db_connection():
    return pymysql.connect(
        host='localhost', user='root', password='password',
        db='classdb', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )

@api.route('/employees')
class Employee(Resource):
    def post(self):
        data = request.json
        conn = get_db_connection()
        with conn.cursor() as cur:
            sql = "INSERT INTO employees (name, department, position) VALUES (%s, %s, %s)"
            cur.execute(sql, (data['name'], data['department'], data['position']))
            conn.commit()
            id = cur.lastrowid
        conn.close()
        return {"id": id}, 201



@app.route('/employees', methods=['GET'])
def get_employees():
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM employees")
        result = cur.fetchall()
    conn.close()
    return jsonify(result)

if __name__ == '__main__':
    app.run(port=5001, debug=True)