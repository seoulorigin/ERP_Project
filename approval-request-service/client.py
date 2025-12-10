import grpc
import approval_pb2
import approval_pb2_grpc

def run():
    with grpc.insecure_channel('localhost:50052') as channel:
    stub = approval_pb2_grpc.ApprovalStub(channel)
    response = stub.RequestApproval(approval_pb2.ReturnApprovalResult(name='DKU'))
    print("Received: " + response.message)

if __name__ == "__main__":
    run()