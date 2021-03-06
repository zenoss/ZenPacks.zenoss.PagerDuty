##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

def enum(**enums):
    enums = dict(enums, ALL=enums.values())
    return type('Enum', (), enums)
