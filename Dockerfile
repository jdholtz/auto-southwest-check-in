FROM python:3.10-alpine

WORKDIR /app

# Used in the script to point to the correct Chromedriver executable
ENV _CHROMEDRIVER_PATH="/usr/bin/chromedriver"

# gcc, libffi-dev, and musl-dev are dependencies needed for building Python wheels
RUN apk add --update --no-cache chromium chromium-chromedriver gcc libffi-dev musl-dev

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
