from concurrent import futures
import grpc, approval_pb2, approval_pb2_grpc

class Approval(approval_pb2_grpc.ApprovalServicer):
    def RequestApproval(self, request, context):
        print("Got request " + str(request))
        return approval_pb2.ApprovalResponse(message='Hello, {0}!'.format(request.name))

def server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    approval_pb2_grpc.add_ApprovalServicer_to_server(Approval(), server)
    server.add_insecure_port('0.0.0.0:50052')
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    server()