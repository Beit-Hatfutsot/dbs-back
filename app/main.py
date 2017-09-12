from bhs_api import create_app

# this file is needed by nginx-uwsgi-flask docker app

app, conf = create_app()

# following can be used for debugging
# if __name__ == "__main__":
#     app.run(host='0.0.0.0', debug=False, port=80)
