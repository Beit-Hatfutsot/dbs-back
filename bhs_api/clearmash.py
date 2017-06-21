from flask import request, abort, current_app, Response

def item_updated():
    current_app.logger.info(request.data)
    return Response()
