import sqlite3 as sql
from codec import encodeAddress32Bit, encodeCouple64Bit

TIMEOUT = 50


def createDatabase(db, schema):
    with sql.connect(db, timeout=TIMEOUT) as conn:
        with open(schema) as f:
            schema = f.readlines()

        cursor = conn.cursor()
        for line in schema:
            cursor.execute(line)
        conn.commit()


def storeTone(db, toneId, toneName, verbose=True):
    with sql.connect(db, timeout=TIMEOUT) as conn:
        print(f"Storing tone {toneId} with name {toneName}")
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tones (toneId, name) VALUES (?, ?)", (toneId, toneName)
            )
        except sql.IntegrityError:
            print("Duplicate tone")
        except Exception as e:
            raise e
            # return

        conn.commit()


def storeAddressCouple(db, addressCouple):
    with sql.connect(db, timeout=TIMEOUT) as conn:
        cursor = conn.cursor()
        for address, couple in addressCouple:
            try:
                cursor.execute(
                    "INSERT INTO addresses (address, couple) VALUES (?, ?)",
                    (encodeAddress32Bit(address), encodeCouple64Bit(couple)),
                )
            except sql.IntegrityError:
                # print("Duplicate address")
                continue
                # return

        conn.commit()


def doesToneExist(db, toneId):
    with sql.connect(db, timeout=TIMEOUT) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tones WHERE toneId = ?", [toneId])
        return cursor.fetchone() is not None


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
