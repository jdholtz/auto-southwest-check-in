FROM python:3.13.0rc2-alpine3.19

WORKDIR /app

# Define so the script knows not to download a new driver version, as
# this Docker image already downloads a compatible chromedriver
ENV AUTO_SOUTHWEST_CHECK_IN_DOCKER=1
ENV PATH="/app/.local/bin:${PATH}"

RUN apk add --update --no-cache chromium chromium-chromedriver xvfb xauth

RUN adduser -D auto-southwest-check-in -h /app
RUN chown -R auto-southwest-check-in:auto-southwest-check-in /app
USER auto-southwest-check-in

COPY requirements.txt .
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
