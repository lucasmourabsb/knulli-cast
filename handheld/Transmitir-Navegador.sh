#!/bin/sh
/usr/bin/python3 /userdata/system/knulli-cast/moonlightctl.py stop
exec /usr/bin/python3 /userdata/system/knulli-cast/server.py start
