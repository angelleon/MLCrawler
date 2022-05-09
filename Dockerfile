FROM python:3.10-bullseye as build
COPY ./src /app
WORKDIR /app
RUN apt update
RUN apt upgrade -y
RUN pip install -y --upgrade pip
RUN pip install -y virtualenv
RUN python -m virtualenv venv
RUN . venv/bin/activate.sh
RUN pip install -r requirements.txt

FROM python:3.10-bullseye as runtime
ARG CATEGORIES="categories.txt"
COPY --from=build /app /app
ENTRYPOINT ["bash", "-c", "source ./venv/bin/activate.sh ; python crawler.py -c $CATEGORIES"]
