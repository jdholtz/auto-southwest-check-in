FROM python:3.12-alpine

WORKDIR /app

# Define so the script knows not to download a new driver version, as
# this Docker image already downloads a compatible chromedriver
ENV AUTO_SOUTHWEST_CHECK_IN_DOCKER=1

# RUN apk add --update --no-cache chromium
# chromium-chromedriver

# Set up glibc
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV GLIBC_REPO=https://github.com/sgerrand/alpine-pkg-glibc
ENV GLIBC_VERSION=2.34-r0
RUN set -ex && \
    apk --update add libstdc++ curl ca-certificates && \
    for pkg in glibc-${GLIBC_VERSION} glibc-bin-${GLIBC_VERSION}; \
        do curl -sSL ${GLIBC_REPO}/releases/download/${GLIBC_VERSION}/${pkg}.apk -o /tmp/${pkg}.apk; done && \
    apk add --allow-untrusted /tmp/*.apk && \
    rm -v /tmp/*.apk && \
    /usr/glibc-compat/sbin/ldconfig /lib /usr/glibc-compat/lib

# Install prerequisites and helper packages
RUN apk add --no-cache \
	bash dpkg xeyes

# Download and unpack Chrome
RUN set -ex && \
	curl -SL https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o /google-chrome-stable_current_amd64.deb && \
	dpkg -x /google-chrome-stable_current_amd64.deb google-chrome-stable && \
	mv /google-chrome-stable/usr/bin/* /usr/bin && \
	mv /google-chrome-stable/usr/share/* /usr/share && \
	mv /google-chrome-stable/etc/* /etc && \
	mv /google-chrome-stable/opt/* /opt && \
	rm -r /google-chrome-stable

# Install Chrome dependencies
RUN apk add --no-cache --update \
	alsa-lib \
	atk \
	at-spi2-atk \
	expat \
	glib \
	gtk+3.0 \
	libdrm \
	libx11 \
	libxcomposite \
	libxcursor \
	libxdamage \
	libxext \
	libxi \
	libxrandr \
	libxscrnsaver \
	libxshmfence \
	libxtst \
	mesa-gbm \
	nss \
	pango

RUN adduser -D auto-southwest-check-in -h /app
USER auto-southwest-check-in

COPY requirements.txt requirements.txt
RUN pip3 install --upgrade pip && pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python3", "-u", "southwest.py"]
