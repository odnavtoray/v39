import os
from waitress import serve
from app import app

if __name__ == "__main__":
    host = os.environ.get("BETA_HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    threads = int(os.environ.get("WAITRESS_THREADS", "8"))
    print(f"Одна Друга Beta v39: http://{host}:{port}")
    print("Production WSGI: Waitress")
    serve(app, host=host, port=port, threads=threads)
