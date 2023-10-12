FROM python:3.12-alpine

WORKDIR /app

# gcompat downloads libraries needed for the chromedriver
RUN apk add --update --no-cache chromium gcompat

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
