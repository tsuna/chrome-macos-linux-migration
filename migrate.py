#!/usr/bin/env python3
# Migrate Chrome profile from macOS to Linux
# Copyright (C) 2024  Benoit Sigoure
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import base64
import json
import os
import sqlite3

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Protocol.KDF import PBKDF2
    from Cryptodome.Util.Padding import pad, unpad
except ImportError:
    try:
        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2
        from Crypto.Util.Padding import pad, unpad
        print("Warning: using pycrypto, consider installing pycryptodome instead")
    except ImportError:
        print("Please install pycryptodome (recommended) or pycrypto")
        raise

MAC_PASSWORD = ''    # From macOS Keychain
SALT = b'saltysalt'  # Hardcoded in Chrome source code
MACOS_KEY = None      # Key used for encryption/decryption on macOS
V10_LINUX_KEY = PBKDF2('peanuts', SALT, dkLen=16, count=1) # Dunno why only 1 iteration on Linux vs 1003 on macOS
IV = b' ' * 16       # Hardcoded IV for AES operations

def set_mac_password(password):
    global MAC_PASSWORD
    global MACOS_KEY
    MAC_PASSWORD = password
    MACOS_KEY = PBKDF2(MAC_PASSWORD, SALT, dkLen=16, count=1003)

def decrypt_string_macos(encrypted_value, key):
    if encrypted_value == b'':
        return ''
    assert encrypted_value[:3] == b'v10', repr(encrypted_value)
    # Remove prefix 'v10'
    encrypted_value = encrypted_value[3:]
    cipher = AES.new(key, AES.MODE_CBC, IV)
    decrypted_value = unpad(cipher.decrypt(encrypted_value), 16)
    return decrypted_value.decode()

def encrypt_string_linux(plaintext):
    if plaintext == '':
        return b''
    cipher = AES.new(V10_LINUX_KEY, AES.MODE_CBC, IV)
    return b'v10' + cipher.encrypt(pad(plaintext.encode('utf-8'), 16))

with open(os.path.expanduser("~/.config/google-chrome/Local State"), encoding="utf-8") as localState:
    profiles = json.load(localState)["profile"]["profiles_order"]
assert profiles, "didn't find any user profiles in Chrome's Local State"

def reencrypt(database, table, column):
    chrome_dir = os.path.expanduser("~/.config/google-chrome")
    for profile in profiles:
        profile_dir = os.path.join(chrome_dir, profile)
        db_path = os.path.join(profile_dir, database)
        print(f"[{profile}] Processing table {table!r} in {database}")
        assert os.path.exists(db_path)
        with sqlite3.connect(db_path) as conn:
            reencrypt_conn(conn, table, column)

def reencrypt_conn(conn, table, column):
    cursor = conn.cursor()

    try:
        cursor.execute(f"DROP TABLE IF EXISTS {table}_temp")
        cursor.execute(f"CREATE TABLE {table}_temp AS SELECT * FROM {table} WHERE 0")
    except:
        print(f"Failed to create temp table {table!r}. The following tables exist:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for name in cursor.fetchall():
            print(f"  - {name}")
        raise

    cursor.execute(f"SELECT * FROM {table}")
    columns = [description[0] for description in cursor.description]
    assert column in columns, f"cannot find column {column} in {table}, only got {columns}"
    placeholders = ', '.join(['?'] * len(columns))

    cnt = 0
    for row in cursor.fetchall():
        cnt += 1
        try:
            entry = dict(zip(columns, row))
            decrypted_value = decrypt_string_macos(entry[column], MACOS_KEY)
            print(f"Processing [#{cnt}]: {table} {row[:3]}")
        except Exception as err:
            print(f"[#{cnt}] Failed to decrypt value for {table} {row[:3]}: {err}")
            raise
        try:
            linux_value = encrypt_string_linux(decrypted_value)
            entry[column] = linux_value
            cursor.execute(f"INSERT INTO {table}_temp ({', '.join(columns)}) VALUES ({placeholders})",
                           list(entry.values()))
            assert cursor.rowcount == 1, f"insert added {cursor.rowcount} rows in {table} {row[:3]}"
        except Exception as err:
            print(f"[#{cnt}] Failed to re-encrypt and update entry for {table} {row[:3]}: {err}")
            raise

    cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_backup")
    cursor.execute(f"ALTER TABLE {table}_temp RENAME TO {table}")
    print(f"Successfully re-encrypted {cnt} rows in {table}")

def main():
    if not MAC_PASSWORD:
        password = input("Enter your Chrome Safe Storage key from macOS Keychain: ")
        if not password:
            print("Password required")
            return
        set_mac_password(password)
        try:
            base64.b64decode(password)
        except ValueError:
            print("Warning: password doesn't look like a base64 encoded string, which it should be.")

    reencrypt('Cookies', 'cookies', 'encrypted_value')
    reencrypt('Safe Browsing Cookies', 'cookies', 'encrypted_value')
    reencrypt('Extension Cookies', 'cookies', 'encrypted_value')
    reencrypt('Login Data', 'logins', 'password_value')
    reencrypt('Login Data For Account', 'logins', 'password_value')
    reencrypt('Web Data', 'credit_cards', 'card_number_encrypted')
    reencrypt('Web Data', 'local_ibans', 'value_encrypted')
    reencrypt('Web Data', 'local_stored_cvc', 'value_encrypted')
    reencrypt('Web Data', 'server_stored_cvc', 'value_encrypted')

if __name__ == '__main__':
    main()
