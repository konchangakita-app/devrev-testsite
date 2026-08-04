import multiprocessing

bind = "0.0.0.0:5020"
worker_class = "uvicorn.workers.UvicornWorker"
workers = 1
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
