FROM ubuntu:22.10

WORKDIR /app

# Needed for python to show logs in all processes
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y python3 python3-pip wget

COPY . .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./utils/chrome-install.py chrome-install.py
RUN python3 chrome-install.py

ENTRYPOINT ["python3", "southwest.py"]
