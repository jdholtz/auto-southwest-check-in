FROM python:3.11-alpine

WORKDIR /app

# gcompat downloads libraries needed for the chromedriver
RUN apk add --update --no-cache chromium gcompat

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

# For some reason, downloading uc_driver results in being detected. Although the chromedriver
# will be automatically downloaded at runtime, it is downloaded now to make sure no version
# discrepancy happens.
RUN sbase get chromedriver

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
