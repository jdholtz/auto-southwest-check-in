FROM ubuntu:latest

ENV SW_USERNAME ""
ENV SW_PASSWORD ""
ENV CONFIRMATION_NUMBER ""
ENV FIRST_NAME ""
ENV LAST_NAME ""

WORKDIR /app

RUN apt-get update && apt-get install -y python3 python3-pip wget
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \ 
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list
RUN apt-get update && apt-get -y install google-chrome-stable

COPY . .

RUN pip3 install -r requirements.txt

CMD ["/app/entrypoint.sh"]
