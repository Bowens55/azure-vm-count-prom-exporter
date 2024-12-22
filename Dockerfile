FROM python:3.11.7-bookworm

WORKDIR /src

COPY ./src/requirements.txt /src/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/ /src/


CMD [ "python", "./main.py" ]