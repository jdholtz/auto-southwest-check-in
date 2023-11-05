FROM python:3.12-alpine

WORKDIR /app

RUN apk add --update --no-cache chromium chromium-chromedriver

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

# Manually copy the driver to the correct locations. There is not currently a chromedriver
# that work with Linux ARM, so it needs to be downloaded through apk and copied over. The
# Python directory will need to be updated every time the Python image is updated.
RUN cp /usr/bin/chromedriver /usr/local/lib/python3.12/site-packages/seleniumbase/drivers/chromedriver
RUN cp /usr/bin/chromedriver /usr/local/lib/python3.12/site-packages/seleniumbase/drivers/uc_driver

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
