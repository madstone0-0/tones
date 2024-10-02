# import sqlite3 as sql
import psycopg as sql
from codec import encodeAddress32Bit, encodeCouple64Bit

TIMEOUT = 50


def createDatabase(db, schema):
    with sql.connect(db) as conn:
        print(f"Connected to {db} info: {conn}")
        with open(schema) as f:
            schema = f.readlines()

        cursor = conn.cursor()
        for line in schema:
            cursor.execute(line)
        conn.commit()


def storeTone(db, toneId, toneName, verbose=True):
    with sql.connect(db) as conn:
        print(f"Storing tone {toneId} with name {toneName}")
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO tone (toneId, name) VALUES (%s, %s)",
                    (toneId, toneName),
                )
            # except sql.IntegrityError:
            #     print("Duplicate tone")
            except Exception as e:
                raise e
                # return

        conn.commit()


def storeAddressCouple(db, addressCouple):
    with sql.connect(db) as conn:
        with conn.cursor() as cursor:
            for address, couple in addressCouple:
                try:
                    cursor.execute(
                        "INSERT INTO address_couple (address, couple) VALUES (%s, %s)",
                        (encodeAddress32Bit(address), encodeCouple64Bit(couple)),
                    )

                except sql.errors.UniqueViolation:
                    continue

            conn.commit()


def doesToneExist(db, toneId):
    with sql.connect(db) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tone WHERE toneId = %s", [toneId])
            return cursor.fetchone() is not None


def readAllAddressCouple(db):
    with sql.connect(db) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM address_couple")
            return cursor.fetchall()


def readAddressCoupleFromAddress(db, address):
    with sql.connect(db) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM address_couple WHERE address = %s", [address])
            return cursor.fetchall()


def readTone(db, toneId):
    with sql.connect(db) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tone WHERE toneId = %s", [toneId])
            return cursor.fetchone()


def readTones(db):
    with sql.connect(db) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tone")
            return cursor.fetchall()
