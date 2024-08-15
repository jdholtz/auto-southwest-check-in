FROM python:3.12-alpine

WORKDIR /app

# Define so the script knows not to download a new driver version, as
# this Docker image already downloads a compatible chromedriver
ENV AUTO_SOUTHWEST_CHECK_IN_DOCKER=1
  
RUN apk add -U --upgrade --no-cache chromium bash bash-completion cmake
# chromium-chromedriver

RUN adduser -D auto-southwest-check-in -h /app
USER auto-southwest-check-in
ENV PATH=$PATH:/app/.local/bin:`chromedriver-path`:/usr/local/lib/python3.12/site-packages/seleniumbase/drivers:/usr/local/lib/python3.12/site-packages/seleniumbase

COPY requirements.txt requirements.txt
RUN python -m pip install --upgrade pip && pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
