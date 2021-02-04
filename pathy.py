#!/usr/bin/python3

import sys
import os


def get_plugin_path(vendor, project):
	reverse_vendor = ".".join(reversed(vendor.split(".")))
	path = f"{sys.prefix}/lib/python{sys.version_info.major}.{sys.version_info.minor}/subpop/{reverse_vendor}.{project}"
	path = os.path.normpath(path)
	return path


print(get_plugin_path("funtoo.org", "powerbus"))
