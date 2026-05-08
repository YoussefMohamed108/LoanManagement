from app import app
from vercel_python import handle

def handler(request):
    return handle(app, request)