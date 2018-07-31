# Copyright 2018 Conversant Design LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import requests, bs4, re, time, sys
from urllib.parse import urlparse

ADOBE_AUTH_URL = 'https://api.auth.adobe.com/api/v1/authenticate'
ADOBE_SAML_RESPONSE_URL = 'https://sp.auth.adobe.com/sp/saml/SAMLAssertionConsumer'
ADOBE_CHECK_AUTHN_URL = 'https://api.auth.adobe.com/api/v1/checkauthn/{}'
IDP_ORIGIN = 'https://sso-idp.evergent.com'
IDP_LOGIN_ACTION_URL = 'https://sso-idp.evergent.com/ad/customerlogin'
PASSWORD_FIELD = 'loginpassword'
USERNAME_FIELD = 'email'
LOGIN_BTN_FIELD = 'login_btn'
MSO_ID = 'ATTOTT' # code for DIRECTV NOW
DEVICE = 'roku'
DEBUG = False # Off by default. Warning: setting to True may result in logging user account credentials

# common headers sent with every request
GLOBAL_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9'
}

# settings specific to the requested channel, supports disney and nick jr currently
CHANNEL_SETTINGS = {
    "disney": {
        'requestor_id': 'DisneyChannels',
        'domain_name': 'adobe.com',
        'redirect_url': lambda code: 'http://disneynow.go.com/activate-congrats?device={}&redirect=true'.format(DEVICE),
        'referer': 'http://disneynow.go.com/activate',
        'origin': 'http://disneynow.go.com'
    },
    "nickjr": {
        'requestor_id': 'NICKJR',
        'domain_name': 'nickjr.com',
        'redirect_url': lambda code: 'http://www.nickjr.com/activate?providerId={}&code={}'.format(MSO_ID, code),
        'referer': 'http://www.nickjr.com/activate',
        'origin': 'http://www.nickjr.com'
    }
}

def unlock(channel_type, code, username, password):
    """ Unlock channel_type using provided activation code and user's credentials to DIRECTV NOW
    - channel_type: currently must be disney or nickjr
    - code: 7 digit uppercase alphanumeric activation code
    - username, password: DIRECTV NOW account credentials
    Exception thrown for any linking failure.
    """
    
    print("Unlocking channel {} with code {}".format(channel_type, code))

    if channel_type not in CHANNEL_SETTINGS:
        raise Exception("Channel type {} not supported".format(channel_type))

    settings = CHANNEL_SETTINGS[channel_type]
    
    with requests.Session() as s:
        s.headers.update(GLOBAL_HEADERS)

        # create SAML request from service provider (Adobe Primetime), and send it to identity provider (Evergent)
        login_request_r = do_saml_request(s, code, settings)

        # Log in through identity provider (Evergent) and generate SAML response
        login_response_r = do_login(s, login_request_r, username, password)

        # Post SAML response back to service provider (Adobe Primetime)
        do_saml_response(s, login_response_r, settings)

        # Check if authentication succeeded
        check_authn(s, code, settings)

    print("Unlock successful for channel {} with code {}".format(channel_type, code))


def do_saml_request(s, code, settings):
    """Send activation code to service provider (Adobe Primetime).
    Input: requests session object, activation code, CHANNEL_SETTINGS settings dict
    Return response object containing login form from identity provider (Evergent).
    Exception thrown on failure.
    """
    params = {
        'reg_code': code,
        'noflash': 'true',
        'mso_id': MSO_ID,
        'requestor_id': settings['requestor_id'],
        'domain_name': settings['domain_name'],
        'redirect_url': settings['redirect_url'](code)
    }
    
    r = get_response(s, ADOBE_AUTH_URL, params, {'Referer': settings['referer']})
    if not (r.status_code == 200 and r.url.lower().startswith(IDP_ORIGIN)):
        log_response(r)
        raise Exception ("SAML request generation failed, status code: {}, returned URL: {}".format(r.status_code, r.url))
        
    return r


def do_login(s, login_request, username, password):
    """ Perform login on identity provider site (Evergent) and get back SAML response.
    Input: requests session object, login_request response object returned from do_saml_request, user's username and password.
    Returns response object containing SAML response.
    Exception thrown on failure.
    """
    
    params = get_hidden_form_params(login_request.text)

    # validate expected hidden form parameters
    if not all (k in params for k in ('id', 'csurl', 'acs_url', 'relayState', 'data', 'MSOID', 'userDevice', 'partnerId', 'partnerIntegrator', 'sessionIndexValue')):
        raise Exception ('Missing expected hidden value in login request form: {}'.format(params))

    params.update({USERNAME_FIELD: username, PASSWORD_FIELD: password, LOGIN_BTN_FIELD: ''})
    r = post_response(s, IDP_LOGIN_ACTION_URL, params, {'Referer': login_request.url, 'Origin': IDP_ORIGIN})
    
    if not (r.status_code == 200 and r.url.lower().startswith(IDP_ORIGIN)):
        log_response(r)
        raise Exception ("Login failed, status code: {}, returned URL: {}".format(r.status_code, r.url))

    return r


def do_saml_response(s, login_response, settings):
    """ Post SAML response back to service provider (Adobe Primetime).
    Input: requests session object, SAML response object, returned from do_login, channel specific dict from CHANNEL_SETTINGS.
    Returned response object is the page the process should redirect back to, regardless of success or failure.
    Actual success is checked in check_authn function, not this function.
    Exception thrown on failure.
    """
    
    params = get_hidden_form_params(login_response.text)
    # validate expected hidden form parameters
    if not all (k in params for k in ('SAMLResponse', 'RelayState')):
        raise Exception ('Missing expected hidden value in login response form: {}'.format(params))
    
    r = post_response(s, ADOBE_SAML_RESPONSE_URL, params, {'Referer': login_response.url, 'Origin': IDP_ORIGIN})
    if not (r.status_code == 200 and r.url.lower().startswith(settings['origin'])):
        log_response(r)
        raise Exception ("SAML response validation failed: status code: {}, returned URL: {}".format(r.status_code, r.url))

    return r

def check_authn(s, code, settings):
    """Verify linking process complete successfully.
    Returns response object with authentication check response from service provider (Adobe Primetime).
    Throws execption on failure.
    """
    params = {'requestor': settings['requestor_id'], '_': int(time.time()*1000) }
    r = get_response(s, ADOBE_CHECK_AUTHN_URL.format(code), params, {'Referer': settings['redirect_url'](code), 'Origin': settings['origin']})

    if r.status_code != 200:
        log_response(r)
        raise Exception ("Auth check failed with status code {}".format(r.status_code))
    
    return r

def post_response(s, url, data, headers):
    """Performs POST to provided URL with provided data (URL form encoded) and provided headers. Does redirect after post if required """
    r = s.post(url, data=data, headers=headers, allow_redirects=False)
    redirect_url = get_redirect_url(r)
    if redirect_url:
        return get_response(s, redirect_url, None, headers = {'Referer':url})
    return r

def get_response(s, url, params, headers, redirects_so_far=0):
    """Performs GET to provided URL with provided query params and headers. Does redirects if necessary (capped at 5 max redirects)."""
    # manually address redirects so we can set cookies and Referer header appropriately in between redirects
    r = s.get(url, params=params, headers=headers, allow_redirects=False)
    redirect_url = get_redirect_url(r)
    
    if redirect_url and redirects_so_far < 5: # max redirects set to 5
        return get_response(s, redirect_url, None, headers={'Referer': url}, redirects_so_far=redirects_so_far+1)
    
    return r

def get_redirect_url(r):
    """Return redirect location in response, if present. Checks for server-side and client-side meta refresh locations"""
    redirect_url = None
    
    # check for server side redirect
    if r.status_code in (301, 302, 307):
        redirect_url = r.headers['Location']
    else:
        # check for client side redirect using meta refresh tag
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        meta_redirect = soup.findAll('meta', attrs={'http-equiv':re.compile('^refresh$', re.I)})
        if len(meta_redirect) > 0:
            _,text = meta_redirect[0]['content'].split(';')
            if text.strip().lower().startswith('url='):
                redirect_url = text[4:]

    # resolve relative redirect url
    if redirect_url is not None and redirect_url.startswith('/'):
        parsed_url = urlparse(r.url)
        redirect_url = '{}://{}{}'.format(parsed_url.scheme, parsed_url.netloc, redirect_url)

    return redirect_url
   
def get_hidden_form_params(content):
    """Extract and return hidden form parameters as dictionary from html page"""
    soup = bs4.BeautifulSoup(content, "html.parser")
    ret = {}
    for f in soup.findAll('input', attrs={'type': 'hidden'}):
        id = f.get('id', f.get('name', ''))
        value = f.get('value', '')
        ret[id] = value
    return ret


# for debugging
def log_response(r):
    if DEBUG:
        # log request
        print('---REQUEST----')
        print(r.request.url)
        print(r.request.headers)
        print(r.body) # Warning: this may contain user's username and password
        print('')
        print('')
        # log response data
        print('---RESPONSE---')
        print (r.url)
        print (r.status_code)
        print (r.headers)
        print (r.cookies.get_dict())
        print (r.text)


# for testing
if __name__ == '__main__':
    unlock(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])


