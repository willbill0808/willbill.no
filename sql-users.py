import sqlite3

connection = sqlite3.connect("users.db")
cursor = connection.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIKE, password TEXT, tier INT) INSERT INTO users (username, password, tier) VALUES (?, ?, ?)", ("guest","guestpass",0))
connection.commit()

for row in cursor.execute("SELECT * FROM users"):
    print(row)

def legg_til():
    navn = input("hva vil du at brukeren din skal hete: ")
    tier = int(input("hvilket tier skal de ha (int): "))
    passord = input("hva vil du at passordet skal være: ")
    print(f"\n {navn=} \n {tier=} \n {passord=}")
    y_n = input("stemmer dette(y/n): ")

    if y_n == "y" or y_n == "yes" or y_n == "ja":
        print("lagrer info")
        cursor.execute("INSERT INTO users (username, password, tier) VALUES (?, ?, ?)", (navn, passord, tier))
        connection.commit()
        return 0
    
    print("lagrer ikke info")
    return 0

legg_til()