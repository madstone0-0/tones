--create database tones;
drop table if exists address_couple;

drop table if exists tone;

create table if not exists address_couple (address bigint, couple bigint);

create table if not exists tone (toneId bigint primary key, name character varying);
