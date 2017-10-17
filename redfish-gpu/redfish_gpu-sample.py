###
# Copyright Notice:
# Copyright 2016 Distributed Management Task Force, Inc. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/python-redfish-library/blob/master/LICENSE.md
###

import sys
import redfish
import re
import json

# When running remotely connect using the address, account name, 
# and password to send https requests
login_host = "https://172.29.100.62"
login_account = "ADMIN"
login_password = "ADMIN"

## Create a REDFISH object
REDFISH_OBJ = redfish.redfish_client(base_url=login_host, username=login_account, \
                          password=login_password, default_prefix='/redfish/v1')

# Login into the server and create a session
REDFISH_OBJ.login(auth="session")

# Do a GET on a given path
response = REDFISH_OBJ.get("/redfish/v1/Chassis/1/Thermal", None)

# Print out the response
#sys.stdout.write("%s\n" % response.dict)
obj=response.dict
for item in obj['Temperatures']:
        name=item['Name']
        regexp=re.compile(r'GPU[0-9] Temp')
        if regexp.search(name):
                sys.stdout.write(item['MemberID'])
                sys.stdout.write('\n')

# Logout of the current session
REDFISH_OBJ.logout()