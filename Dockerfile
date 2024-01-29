FROM ubuntu:20.04
ENV DEBIAN_FRONTEND="noninteractive" TZ="America/New_York"
ENV FLASK_APP="run.py"
ENV FLASK_ENV="development"


COPY run.py  /dashboard/
COPY requirements.txt  /dashboard/
COPY config.py  /dashboard/
ADD app /dashboard/app
RUN mkdir -p /dashboard/cache-dir

RUN apt update && apt install vim tzdata python3 python3-pip -y
RUN pip3 install -r /dashboard/requirements.txt

#LAUNCH upon startup
CMD  cd /dashboard && flask run --host=0.0.0.0  --port=5000
