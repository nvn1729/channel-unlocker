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

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_model.ui import SimpleCard
from ask_sdk_model.slu.entityresolution.status_code import StatusCode
from ask_sdk_core.utils import is_request_type, is_intent_name
import unlocker, json, sys, os


# Constants/format strings used as part of message responses

INVOCATION_NAME = "Channel Unlocker"
LAUNCH_WELCOME_MESSAGE = "Welcome to {}! Do you want to unlock Disney or Nick Jr?".format(INVOCATION_NAME)
CHANNEL_REPROMPT_MESSAGE = "Do you want to unlock Disney or Nick Jr?"
CHANNEL_ERROR_MESSAGE = "Please choose either Disney or Nick Jr."
CODE_MESSAGE = "Ok, what's the activation code?"
CODE_REPROMPT_MESSAGE = "What's the activation code?"
CODE_ERROR_MESSAGE = "That's an invalid code. Please try again."
GOODBYE_MESSAGE = "Goodbye!"
HELP_MESSAGE = "Choose the channel and provide the activation code."
ERROR_MESSAGE = "Sorry, I didn't understand that, what did you say?"
CARD_TITLE = INVOCATION_NAME
CARD_TITLE_DONE = GOODBYE_MESSAGE
CARD_TITLE_HELP = "Help"
SESSION_STATE_KEY = "STATE"
CHANNEL_SLOT_NAME = "Channel"
CODE_SLOT_NAMES = ["DigitOne", "DigitTwo", "DigitThree", "DigitFour", "DigitFive", "DigitSix", "DigitSeven"]
CODE_NUMBER_MAP = { "ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5", "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9"}
UNLOCK_SUCCESS_MESSAGE = "Done. Goodbye!"
UNLOCK_FAILURE_MESSAGE = "The channel could not be unlocked. Please try again. Goodbye!"
USERNAME = "USERNAME"
PASSWORD = "PASSWORD"


# Helper function
def launch(handler_input):
    """Start skill"""

    # set empty state
    handler_input.attributes_manager.session_attributes[SESSION_STATE_KEY] = {}
    handler_input.response_builder.speak(LAUNCH_WELCOME_MESSAGE).ask(CHANNEL_REPROMPT_MESSAGE).set_card(SimpleCard(CARD_TITLE, CHANNEL_REPROMPT_MESSAGE)).set_should_end_session(False)
    
    return handler_input.response_builder.response
                                                                                                       

# Request handlers, covering the following intents:
# LaunchRequest
# IntentRequest: ChannelIntent, CodeIntent, HelpIntent, StopIntent, CancelIntent, FallbackIntent
# SessionEndedRequest

sb = SkillBuilder()


@sb.request_handler(can_handle_func=is_request_type("LaunchRequest"))    
def launch_request_handler(handler_input):
    """Launch Request"""
    return launch(handler_input)

@sb.request_handler(can_handle_func=is_intent_name("ChannelIntent"))
def channel_intent_handler(handler_input):
    """Accept name of channel to unlock"""

    channel = handler_input.request_envelope.request.intent.slots[CHANNEL_SLOT_NAME].value.lower()
    if channel.startswith("nick"):
        channel = "nickjr"
        
    if channel not in unlocker.CHANNEL_SETTINGS:
        # unrecognized channel, ask for channel again
        handler_input.response_builder.speak(CHANNEL_ERROR_MESSAGE).ask(CHANNEL_REPROMPT_MESSAGE).set_card(SimpleCard(CARD_TITLE, CHANNEL_REPROMPT_MESSAGE)).set_should_end_session(False)
    else:
        # save channel in session and ask for activation code
        handler_input.attributes_manager.session_attributes[SESSION_STATE_KEY] = {"channel": channel }
        handler_input.response_builder.speak(CODE_MESSAGE).ask(CODE_REPROMPT_MESSAGE).set_card(SimpleCard(CARD_TITLE, CODE_REPROMPT_MESSAGE)).set_should_end_session(False)
    
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("CodeIntent"))
def code_intent_handler(handler_input):
    """Get user's activation code and use it to unlock previously provided channel to account"""
    try:
        state = handler_input.attributes_manager.session_attributes[SESSION_STATE_KEY]
    except:
        # out of session request, launch the skill
        return launch(handler_input)

    # channel is missing, ask for it again
    if 'channel' not in state:
        handler_input.response_builder.speak(CHANNEL_ERROR_MESSAGE).ask(CHANNEL_REPROMPT_MESSAGE).set_card(SimpleCard(CARD_TITLE, CHANNEL_REPROMPT_MESSAGE)).set_should_end_session(False)
        return handler_input.response_builder.response

    # build activation code from code intent slots
    code = ''
    try:
        for slot in CODE_SLOT_NAMES:
            code_digit_slot = handler_input.request_envelope.request.intent.slots[slot]
            code_digit_resolution = code_digit_slot.resolutions.resolutions_per_authority[0]
            code_digit = ''
            
            if code_digit_resolution.status.code == StatusCode.ER_SUCCESS_MATCH:
                code_digit = code_digit_resolution.values[0].value.name.upper()
                
            if code_digit in CODE_NUMBER_MAP:
                code_digit = CODE_NUMBER_MAP[code_digit]
            elif len(code_digit) > 1:
                code_digit = code_digit[0]

            if code_digit.isupper() or code_digit.isdigit():
                code += code_digit

    except:
        # invalid code digit or missing slot value
        pass

    # invalid code, ask for code again
    if len(code) != 7:
        handler_input.response_builder.speak(CODE_ERROR_MESSAGE).ask(CODE_REPROMPT_MESSAGE).set_card(SimpleCard(CARD_TITLE, CODE_REPROMPT_MESSAGE)).set_should_end_session(False)
        return handler_input.response_builder.response

    # try to unlock account now
    try:
        unlocker.unlock(state['channel'], code, os.environ[USERNAME], os.environ[PASSWORD])
        card_message = "Channel {} was unlocked with activation code {}".format(state['channel'], code)
        handler_input.response_builder.speak(UNLOCK_SUCCESS_MESSAGE).set_card(SimpleCard(CARD_TITLE_DONE, card_message)).set_should_end_session(True)
    except:
        card_message = "Channel {} could not be unlocked with activation code {}".format(state['channel'], code)
        handler_input.response_builder.speak(UNLOCK_FAILURE_MESSAGE).set_card(SimpleCard(CARD_TITLE_DONE, card_message)).set_should_end_session(True)
    
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.FallbackIntent"))
def fallback_intent_handler(handler_input):
    """ Fallback intent handler """
    try:
        _ = handler_input.attributes_manager.session_attributes[SESSION_STATE_KEY]
        handler_input.response_builder.speak(ERROR_MESSAGE).ask(ERROR_MESSAGE).set_should_end_session(False)
        return handler_input.response_builder.response
    except:
        # out of session request, launch skill
        return launch(handler_input)


@sb.request_handler(can_handle_func=is_intent_name("AMAZON.HelpIntent"))
def help_intent_handler(handler_input):
    """ Help intent handler """
    try:
        _ = handler_input.attributes_manager.session_attributes[SESSION_STATE_KEY]
        handler_input.response_builder.speak(HELP_MESSAGE).set_card(SimpleCard(CARD_TITLE_HELP, HELP_MESSAGE)).set_should_end_session(False)
        return handler_input.response_builder.response
    except:
        # out of session request, launch skill
        return launch(handler_input)


@sb.request_handler(
    can_handle_func=lambda input:
        is_intent_name("AMAZON.CancelIntent")(input) or
        is_intent_name("AMAZON.StopIntent")(input))
def cancel_and_stop_intent_handler(handler_input):
    """ Cancel and stop intents: just say goodbye."""
    
    handler_input.response_builder.speak(GOODBYE_MESSAGE).set_card(
        SimpleCard(INVOCATION_NAME, GOODBYE_MESSAGE))
    return handler_input.response_builder.response


@sb.request_handler(can_handle_func=is_request_type("SessionEndedRequest"))
def session_ended_handler(handler_input):
    return handler_input.response_builder.response


# Global exception handler

@sb.exception_handler(can_handle_func=lambda i, e: True)
def all_exception_handler(handler_input, exception):
    """Log the exception to CloudWatch, and return a generic error response."""
    
    print("Encountered following exception: {}".format(exception))
    handler_input.response_builder.speak(ERROR_MESSAGE).ask(ERROR_MESSAGE)
    return handler_input.response_builder.response


# Interceptors for request and response logging

@sb.global_request_interceptor()
def log_request(handler_input):
    """Log request to CloudWatch"""
    print("Skill request: {}\n".format(handler_input.request_envelope.request))

@sb.global_response_interceptor()
def log_response(handler_input, response):
    """Log response to CloudWatch"""
    print("Skill response: {}\n".format(response))


# handler is the lambda function entry point.
handler = sb.lambda_handler()


# For testing only: Invoke lambda handler on event contained in a file in JSON format.
if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        event = json.load(f)
        handler(event, None)
