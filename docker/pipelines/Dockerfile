FROM frictionlessdata/datapackage-pipelines

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY *.py /pipelines/
COPY pipeline-spec.yaml /pipelines/
