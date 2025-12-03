from flask import Flask, request, jsonify
from flask_restx import Api, Resource, reqparse
import pymysql

app = Flask(__name__)
api = Api(app)

parser = reqparse.RequestParser()
parser.add_argument('name', type=str, location='args')
parser.add_argument('department', type=str, location='args')
parser.add_argument('position', type=str, location='args')

def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='password',
        db='classdb',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor # 결과를 dict 형식으로 받음
    )

# TODO: 필드 검증 후 INSERT 실행
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

    def get(self):
        conn = get_db_connection()
        args = parser.parse_args()
        with conn.cursor() as cur:
            sql = "SELECT * FROM employees WHERE 1=1"
            params = []

            if args['name']:
                sql += " AND name = %s"
                params.append(args['name'])

            if args['department']:
                sql += " AND department = %s"
                params.append(args['department'])

            if args['position']:
                sql += " AND position = %s"
                params.append(args['position'])

            cur.execute(sql, tuple(params))
            result = cur.fetchall()
        conn.close()
        ret = []
        for row in result:
            ret.append({"id": row['id'], "name": row['name'], "department": row['department'], "position": row['position']})

        return ret, 200

if __name__ == '__main__':
    app.run(port=5001, debug=True)