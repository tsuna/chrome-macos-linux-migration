# chrome-macos-linux-migration
**Migrate Chrome data, profiles, cookies, passwords, etc from macOS to Linux**

Use case: you have been using Chrome on macOS and you want to start using
Chrome on Linux (whether in a VM or natively) and you want to preserve
everything as you migrate over to Linux.

Usage steps:
1. Install Linux
2. Install Chrome on Linux
3. Start Chrome on Linux to initialize a default profile
4. Close Chrome on both Linux and macOS
5. Copy your `~/Library/Application\ Support/Google/Chrome` onto Linux
6. Run `./migrate.py`
7. The script will prompt you for your *Chrome Safe Storage* key, which you
   can get from Keychain Access on macOS
8. Start Chrome on Linux, all your tabs and sessions should re-open as-is

The script will then proceed to decrypt and re-encrypt various data stored in
SQLite, including cookies, login data (saved passwords), other securely stored
web data such as saved credit card information.

**Use at your own risk, always backup your data first!**

Note: Google seems to detect the shenanigans and will log you out forcefully,
which is a bit annoying.

If you keep using Chrome on macOS and want to regularly sync with Linux, use
`rsync` to copy incremental deltas over from macOS to Linux, just remember to
delete the files `SingletonCookie`, `SingletonLock`, `SingletonSocket` on
Linux before starting Chrome again. And Google will log you out again.
