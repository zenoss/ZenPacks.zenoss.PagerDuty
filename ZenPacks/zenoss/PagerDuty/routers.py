##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import requests
import models.account
import models.service

from Products.ZenUtils.Ext import DirectRouter, DirectResponse

import logging
log = logging.getLogger('zen.PagerDuty.ServicesRouter')

ACCOUNT_ATTR = 'pagerduty_account'

def _dmdRoot(dmdContext):
    return dmdContext.getObjByPath("/zport/dmd/")

def _retrieveServices(account):
    log.info("Fetching list of PagerDuty services for %s..." % account.fqdn())
    try:
        apiServices = requests.retrieveServices(account)

    except requests.InvalidTokenException as e:
        log.warn("Token rejected")
        raise
    except requests.PagerDutyUnreachableException as e:
        log.warn("PagerDuty not reachable: %s" % e.message)
        raise
    except requests.ParseException as e:
        log.warn(e.message)
        raise

    log.info("Found %d services with integration of Events API V2  for %s" % (len(apiServices), account.fqdn()))
    return apiServices

class AccountRouter(DirectRouter):
    def __init__(self, context, request=None):
        super(AccountRouter, self).__init__(context, request)

    def getAccountSettings(self):
        """
        Retrieves the account object from /zport/dmd/pagerduty_account.
        """
        dmdRoot = _dmdRoot(self.context)
        account = getattr(dmdRoot, ACCOUNT_ATTR, models.account.Account(None, None))
        return DirectResponse.succeed(msg=None, data=account.getDict())

    def updateAccountSettings(self, apiAccessKey=None, subdomain=None, apiTimeout=None, wantsMessages=True):
        """
        Saves the account object and returns a list of services associated
        with that account.  Returns nothing if invalid account info is set.

        The account object is saved as /zport/dmd/pagerduty_account
        (aka, dmdRoot.pagerduty_account)
        """
        if not apiAccessKey or not subdomain:
            return DirectResponse.fail(msg="Api Access Key and subdomain are needed for PagerDuty account")

        if not apiTimeout:
            account = models.account.Account(subdomain, apiAccessKey)
            log.info("The API Timeout zero value results in a default timeout of 40 seconds")
        else:
            account = models.account.Account(subdomain, apiAccessKey, int(apiTimeout))

        dmdRoot = _dmdRoot(self.context)
        setattr(dmdRoot, ACCOUNT_ATTR, account)

        servicesRouter = ServicesRouter(self.context, self.request)
        result = servicesRouter.getServices(wantsMessages)

        if result.data['success']:
            result.data['msg'] = "PagerDuty services retrieved successfully."
            apiServices = result.data['data']
            log.info("Successfully fetched %d PagerDuty generic API services.", len(apiServices))

        return result

class ServicesRouter(DirectRouter):
    """
    Simple router responsible for fetching the list of services from PagerDuty.
    """
    def getServices(self, wantsMessages=False):
        dmdRoot = _dmdRoot(self.context)
        noAccountMsg = 'PagerDuty account info not set.'
        setUpApiKeyInlineMsg = 'Set up your account info in "Advanced... PagerDuty Settings"'
        msg = noAccountMsg if wantsMessages else None
        if not hasattr(dmdRoot, ACCOUNT_ATTR):
            return DirectResponse.fail(msg=msg, inlineMessage=setUpApiKeyInlineMsg)

        account = getattr(dmdRoot, ACCOUNT_ATTR)
        if not account.apiAccessKey or not account.subdomain:
            return DirectResponse.fail(msg=msg, inline_message=setUpApiKeyInlineMsg)

        try:
            apiServices = _retrieveServices(account)
        except requests.InvalidTokenException:
            msg = 'Your API Access Key was denied.' if wantsMessages else None
            return DirectResponse.fail(msg=msg, inline_message='Access key denied: Go to "Advanced... PagerDuty Settings"')
        except requests.PagerDutyUnreachableException as pdue:
            msg = pdue.message if wantsMessages else None
            return DirectResponse.fail(msg=msg, inline_message=pdue.message)

        if not apiServices:
            msg = ("No services with events integration v2 were found for %s.pagerduty.com." % account.subdomain) if wantsMessages else None
            return DirectResponse.fail(msg=msg)

        data = [service.getDict() for service in apiServices]
        return DirectResponse.succeed(msg=None, data=data)
