FROM python:3.6

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt ; \
    pip install --no-cache-dir -r requirements-test.txt


CMD [ "pytest" ]
