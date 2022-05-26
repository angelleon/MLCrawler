FROM python:3.10-bullseye as build
COPY ./src /app
COPY requirements.txt /app/
WORKDIR /app
RUN apt-get update
RUN apt-get upgrade -y
RUN pip install --upgrade pip
RUN pip install virtualenv
RUN python -m virtualenv venv
RUN . venv/bin/activate
RUN pip install -r requirements.txt

FROM python:3.10-bullseye as runtime
ARG CATEGORIES="categories.txt"
COPY --from=build /app /app
ENTRYPOINT ["bash", "-c", "source ./venv/bin/activate.sh ; python crawler.py -c $CATEGORIES"]
