FROM python:3.11

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

RUN chmod +x app/flights/start.sh

CMD ["./app/flights/start.sh"]