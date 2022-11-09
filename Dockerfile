FROM ubuntu:22.10

WORKDIR /app

# Needed for python to show logs in all processes
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y python3 python3-pip wget

# Download google-chrome
RUN wget https://dl-ssl.google.com/linux/linux_signing_key.pub -O /tmp/google.pub && \
    gpg --no-default-keyring --keyring /etc/apt/keyrings/google-chrome.gpg --import /tmp/google.pub && \
    echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main' | \
    tee /etc/apt/sources.list.d/google-chrome.list
    
RUN apt-get update && apt-get -y install google-chrome-stable

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "southwest.py"]


