FROM ubuntu:22.10

WORKDIR /app

# Needed for python to show logs in all processes
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y python3 python3-pip wget

# Download google-chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
RUN apt-get update && apt-get -y install google-chrome-stable

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["/app/entrypoint.sh"]
