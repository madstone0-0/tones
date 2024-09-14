import sqlite3 as sql
from codec import encodeAddress32Bit, encodeCouple64Bit


def createDatabase(db, schema):
    with sql.connect(db) as conn:
        with open(schema) as f:
            schema = f.readlines()

        cursor = conn.cursor()
        for line in schema:
            cursor.execute(line)
        conn.commit()


def storeTone(db, toneId, toneName):
    with sql.connect(db) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tones (toneId, name) VALUES (?, ?)", (toneId, toneName)
            )
        except sql.IntegrityError:
            print("Duplicate tone")
            # return

        conn.commit()


def storeAddressCouple(db, addressCouple):
    with sql.connect(db) as conn:
        cursor = conn.cursor()
        for address, couple in addressCouple:
            try:
                cursor.execute(
                    "INSERT INTO addresses (address, couple) VALUES (?, ?)",
                    (encodeAddress32Bit(address), encodeCouple64Bit(couple)),
                )
            except sql.IntegrityError:
                print("Duplicate address")
                continue
                # return

        conn.commit()


def readAllAddressCouple(db):
    with sql.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM addresses")
        return cursor.fetchall()


def readAddressCoupleFromAddress(db, address):
    with sql.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM addresses WHERE address = ?", [address])
        return cursor.fetchall()


def readTone(db, toneId):
    with sql.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tones WHERE toneId = ?", [toneId])
        return cursor.fetchone()


def readTones(db):
    with sql.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tones")
        return cursor.fetchall()
