\c tickets

\c flights

insert into airport(name,city,country) values ('Шереметьево', 'Москва', 'Россия'),('Пулково', 'Санкт-Петербург', 'Россия');

insert into flight(flight_number,datetime,from_airport_id,to_airport_id,price) values (
    'AFL031',
    '2021-10-08 20:00',
    (select id from airport where name = 'Пулково'),
    (select id from airport where name = 'Шереметьево'),
    1500
);

\c privileges

insert into privilege(username, balance) values
    ('Test Max', 0);

\c tickets
insert into ticket (ticket_uid, username, flight_number, price, status) values
    ('550e8400-e29b-41d4-a716-446655440000', 'Test Max', 'AFL031', 1500, 'PAID');