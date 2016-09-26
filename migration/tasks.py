from celery import Celery

app = Celery('migration.tasks', broker='redis://guest@localhost//')

@app.task
def update_row(row):
    return x + y
