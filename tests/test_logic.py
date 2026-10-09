"""Offline logic tests. ASK SDK and HTTP are stubbed; not an Alexa integration test."""
from pathlib import Path
import ast
import json
import logging
import re
from html import escape
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
import requests

ROOT = Path(__file__).resolve().parents[1]
LAMBDA_FILE = ROOT / 'lambda' / 'lambda_function.py'
ARABIC_MODEL = ROOT / 'skill-package' / 'interactionModels' / 'custom' / 'ar-SA.json'

class ResponseBuilder:
    def __init__(self):
        self.output = {}
    def speak(self, text):
        self.output['speech'] = text
        return self
    def ask(self, text):
        self.output['reprompt'] = text
        self.output['should_end_session'] = False
        return self
    @property
    def response(self):
        return dict(self.output)

class SkillBuilder:
    def __init__(self):
        self.handlers = []
        self.exception_handlers = []
    def add_request_handler(self, handler):
        self.handlers.append(handler)
    def add_exception_handler(self, handler):
        self.exception_handlers.append(handler)
    def lambda_handler(self):
        return None  # SDK serialization/dispatch is outside this test's scope.


def load_logic():
    tree = ast.parse(LAMBDA_FILE.read_text())
    # Use the actual source for all functions/classes; replace only imports/framework.
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    fake_http = SimpleNamespace(post=Mock())
    utils = SimpleNamespace(
        is_intent_name=lambda name: lambda h: (
            h.request_envelope.request.type == 'IntentRequest'
            and h.request_envelope.request.intent.name == name),
        is_request_type=lambda kind: lambda h: h.request_envelope.request.type == kind,
    )
    env = dict(AbstractRequestHandler=object, AbstractExceptionHandler=object,
               SkillBuilder=SkillBuilder, requests=fake_http, ask_utils=utils,
               logging=logging, json=json, re=re, escape=escape,
               __name__='jamal_logic_under_test')
    exec(compile(tree, 'lambda_function.py', 'exec'), env)
    return env, fake_http


def input_for(intent=None, query='احچيلي عن تاريخ بغداد', *, kind='IntentRequest', slots=True, attributes=None):
    slot_map = {'query': SimpleNamespace(value=query)} if slots else None
    request = SimpleNamespace(type=kind, locale='ar-SA', intent=SimpleNamespace(name=intent, slots=slot_map))
    return SimpleNamespace(request_envelope=SimpleNamespace(request=request),
                           attributes_manager=SimpleNamespace(session_attributes=attributes if attributes is not None else {}),
                           response_builder=ResponseBuilder())

class JamalLogicTests(unittest.TestCase):
    def setUp(self):
        self.env, self.http = load_logic()
        self.http.post.return_value = SimpleNamespace(
            ok=True, status_code=200,
            json=lambda: {'choices':[{'message':{'content':'هذا جواب عربي.'}}]})

    def dispatch(self, h):
        handlers = [x for x in self.env['sb'].handlers if x.can_handle(h)]
        self.assertEqual(len(handlers),1)
        return handlers[0].handle(h)

    def test_arabic_query_reaches_model_unchanged(self):
        h = input_for('GptQueryIntent')
        result = self.dispatch(h)
        self.assertIn('جواب عربي', result['speech'])
        self.assertEqual(self.http.post.call_count, 1)
        payload = json.loads(self.http.post.call_args.kwargs['data'])
        self.assertEqual(payload['model'],'gpt-4o-mini')
        self.assertEqual(payload['messages'][-1]['content'],'احچيلي عن تاريخ بغداد')
        self.assertIn('Iraqi Arabic',payload['messages'][0]['content'])
        self.assertEqual(len(h.attributes_manager.session_attributes['chat_history']), 1)
        self.assertEqual(self.http.post.call_args.kwargs['timeout'],(1,5))

    def test_missing_slots_no_model_call(self):
        result = self.dispatch(input_for('GptQueryIntent', slots=False))
        self.assertIn('ما وصلني',result['speech'])
        self.http.post.assert_not_called()

    def test_empty_query_no_model_call(self):
        for query in [None, '', '   ']:
            result = self.dispatch(input_for('GptQueryIntent',query=query))
            self.assertIn('ما وصلني', result['speech'])
        self.http.post.assert_not_called()

    def test_all_model_intents_have_exactly_one_handler(self):
        model = json.loads(ARABIC_MODEL.read_text())
        for intent in model['interactionModel']['languageModel']['intents']:
            with self.subTest(intent=intent['name']):
                h = input_for(intent['name'])
                self.assertEqual(sum(handler.can_handle(h) for handler in self.env['sb'].handlers),1)

    def test_fallback_does_not_send_missing_transcript(self):
        result = self.dispatch(input_for('AMAZON.FallbackIntent',slots=False))
        self.assertIn('ما فهمت',result['speech'])
        self.http.post.assert_not_called()

    def test_help_in_arabic(self):
        result = self.dispatch(input_for('AMAZON.HelpIntent',slots=False))
        self.assertIn('جمال',result['speech'])
        self.http.post.assert_not_called()

    def test_launch_has_arabic_greeting(self):
        result = self.dispatch(input_for(kind='LaunchRequest'))
        self.assertIn('هلا بيك', result['speech'])
        self.http.post.assert_not_called()

    def test_session_end_does_not_speak(self):
        self.assertNotIn('speech',self.dispatch(input_for(kind='SessionEndedRequest')))
        self.http.post.assert_not_called()

    def test_stop_cancel_home(self):
        for name in ['AMAZON.StopIntent','AMAZON.CancelIntent','AMAZON.NavigateHomeIntent']:
            result = self.dispatch(input_for(name))
            self.assertEqual(result['speech'],'مع السلامة.')
            self.assertNotIn('reprompt',result)

    def test_clear_context_preserves_original_scope(self):
        attributes = {'chat_history': [('old','answer')], 'last_context': {'question':'old'}}
        result = self.dispatch(input_for('ClearContextIntent',attributes=attributes))
        self.assertEqual(attributes['chat_history'],[])
        self.assertIsNone(attributes['last_context'])
        self.assertIn('بهالجلسة',result['speech'])

    def test_xml_special_characters_are_escaped(self):
        self.http.post.return_value.json = lambda: {'choices':[{'message':{'content':'هذا <اختبار> & جواب'}}]}
        result = self.dispatch(input_for('GptQueryIntent'))
        self.assertEqual(result['speech'],'هذا &lt;اختبار&gt; &amp; جواب')

    def test_api_error_is_not_spoken_verbatim(self):
        self.http.post.return_value = SimpleNamespace(ok=False,status_code=401,json=lambda:{'error':{'message':'PRIVATE_API_ERROR'}})
        result = self.dispatch(input_for('GptQueryIntent'))
        self.assertIn('خلل',result['speech'])
        self.assertNotIn('PRIVATE_API_ERROR',result['speech'])

    def test_timeout_is_not_spoken_verbatim(self):
        self.http.post.side_effect = requests.Timeout('PRIVATE_DETAIL')
        result = self.dispatch(input_for('GptQueryIntent'))
        self.assertIn('خلل',result['speech'])
        self.assertNotIn('PRIVATE_DETAIL',result['speech'])

    def test_default_followup_function_makes_no_api_call(self):
        self.assertEqual(self.env['generate_followup_questions']([], 'سؤال','جواب'),[])
        self.http.post.assert_not_called()

    def test_searchquery_has_carrier_phrases(self):
        model = json.loads(ARABIC_MODEL.read_text())['interactionModel']['languageModel']
        intent = next(x for x in model['intents'] if x['name']=='GptQueryIntent')
        self.assertEqual(intent['slots'],[{'name':'query','type':'AMAZON.SearchQuery'}])
        for sample in intent['samples']:
            self.assertIn('{query}',sample)
            self.assertTrue(sample.replace('{query}','').strip())

if __name__ == '__main__':
    unittest.main(verbosity=2)
