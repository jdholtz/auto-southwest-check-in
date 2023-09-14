FROM python:3.11-alpine

WORKDIR /app

RUN apk add --update --no-cache chromium chromium-chromedriver

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
