# midea-ac-py

This is an overly complicated set of tools to allow communicating to a Midea AC via the Midea Cloud.

This is a very early release, and comes without any guarantees. Please don't log any bugs yet, this is still an early work in progress and simply serves as a proof of concept.

This library is a direct ripoff from the amazing work done by Yitsushi and his Ruby based command line tool for the same purpose. You can find his work here: https://github.com/yitsushi/midea-air-condition
The reasons for me converting this to Python is that I am planning on changing this into a Home Assistant plugin soon.

To run a test, you have to edit mideaclient.py and change the lines setting the appKey, username and password. You can get hte appKey from an APK, and the username is your Midea registered email address, and the password for your account.
