from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils
import requests
import logging
import json
import re
from html import escape

# Set your OpenAI API key

api_key = "YOUR_API_KEY"

model = "gpt-4o-mini"

# Keep the original follow-up function, but avoid a second model request by default.
ENABLE_FOLLOWUP_SUGGESTIONS = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "هلا بيك، وياك جمال. كلي مثلا: جمال احچيلي عن تاريخ بغداد."

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class GptQueryIntentHandler(AbstractRequestHandler):
    """Handler for Gpt Query Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        request = handler_input.request_envelope.request
        slots = request.intent.slots or {}
        query_slot = slots.get("query")
        query = (query_slot.value or "").strip() if query_slot else ""

        # Log routing metadata only, not private conversations or credentials.
        logger.info("locale=%s intent=%s query_present=%s",
                    request.locale, request.intent.name, bool(query))
        if not query:
            speak_output = "ما وصلني سؤالك. كلي مثلا: جمال احچيلي عن تاريخ بغداد."
            return (handler_input.response_builder
                    .speak(speak_output)
                    .ask("كلي جمال، وبعدها سؤالك.")
                    .response)

        session_attr = handler_input.attributes_manager.session_attributes
        if "chat_history" not in session_attr:
            session_attr["chat_history"] = []
            session_attr["last_context"] = None
        
        # Process the query to determine if it's a follow-up question
        processed_query, is_followup = process_followup_question(query, session_attr.get("last_context"))
        
        # Generate response with enhanced context handling
        response_data = generate_gpt_response(session_attr["chat_history"], processed_query, is_followup)
        
        # Handle the response data which could be a tuple or string
        if isinstance(response_data, tuple) and len(response_data) == 2:
            response_text, followup_questions = response_data
        else:
            # Fallback for error cases
            response_text = str(response_data)
            followup_questions = []
        
        # Store follow-up questions in the session
        session_attr["followup_questions"] = followup_questions
        
        # Update the conversation history with just the response text, not the questions
        session_attr["chat_history"].append((query, response_text))
        session_attr["last_context"] = extract_context(query, response_text)
        
        # Format the response with follow-up suggestions if available
        response = escape(response_text, quote=False)
        if followup_questions and len(followup_questions) > 0:
            # Add a short pause before the suggestions
            response += " <break time=\"0.5s\"/> "
            response += "تكدر تسأل: "
            # Join with 'or' for the last question
            if len(followup_questions) > 1:
                response += ", ".join([f"'{escape(q, quote=False)}'" for q in followup_questions[:-1]])
                response += f"، أو '{escape(followup_questions[-1], quote=False)}'"
            else:
                response += f"'{escape(followup_questions[0], quote=False)}'"
            response += ". <break time=\"0.5s\"/>"
        
        # Prepare response with reprompt that includes the follow-up questions
        reprompt_text = "كلي جمال، وبعدها سؤالك، أو كلي توقف."
        if 'followup_questions' in session_attr and session_attr['followup_questions']:
            reprompt_text = "كلي جمال، وبعدها سؤالك، أو كلي توقف."
        
        return (
            handler_input.response_builder
                .speak(response)
                .ask(reprompt_text)
                .response
        )

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors."""
    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error("Unhandled Alexa request: %s", type(exception).__name__)

        speak_output = "صار خلل بسيط. كلي جمال، وبعدها عيد سؤالك."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.NavigateHomeIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "مع السلامة."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

def process_followup_question(question, last_context):
    """Processes a question to determine if it's a follow-up and enhances it with context if needed"""
    # Common follow-up indicators
    followup_patterns = [
        r'^(what|how|why|when|where|who|which)\s+(about|is|are|was|were|do|does|did|can|could|would|should|will)\s',
        r'^(and|but|so|then|also)\s',
        r'^(can|could|would|should|will)\s+(you|it|they|we)\s',
        r'^(is|are|was|were|do|does|did)\s+(it|that|this|they|those|these)\s',
        r'^(tell me more|elaborate|explain further)\s*',
        r'^(why|how)\?*$'
    ]
    
    is_followup = False
    
    # Check if the question matches any follow-up patterns
    for pattern in followup_patterns:
        if re.search(pattern, question.lower()):
            is_followup = True
            break
    
    # If it's a follow-up and we have context, we don't need to modify the question
    # The context will be handled in the generate_gpt_response function
    return question, is_followup

def extract_context(question, response):
    """Extracts the main context from a Q&A pair for future reference"""
    # This is a simple implementation that just returns the question and response
    # In a more advanced implementation, you could use NLP to extract key entities
    return {"question": question, "response": response}

def generate_followup_questions(conversation_context, query, response, count=2):
    """Generates concise follow-up questions based on the conversation context."""
    if not ENABLE_FOLLOWUP_SUGGESTIONS:
        return []
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        url = "https://api.openai.com/v1/chat/completions"
        
        # Prepare a focused prompt for brief follow-ups
        messages = [
            {"role": "system", "content": "اقترح أسئلة متابعة قصيرة باللهجة العراقية فقط، بدون شرح."},
            {"role": "user", "content": """اقترح سؤالين قصيرين باللهجة العراقية، كل سؤال أربع كلمات كحد أقصى.
            رجع الأسئلة فقط وافصل بينها بعلامة |.
            مثال: احچيلي أكثر|عندك مثال"""}
        ]
        
        # Add conversation context
        if conversation_context:
            last_q, last_a = conversation_context[-1]
            messages.append({"role": "user", "content": f"Previous Q: {last_q}"})
            messages.append({"role": "assistant", "content": last_a})
        
        messages.append({"role": "user", "content": f"Current Q: {query}"})
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": "أسئلة المتابعة بالعراقي، مفصولة بعلامة |:"})
        
        data = {
            "model": "gpt-3.5-turbo",  # Using a faster model for this
            "messages": messages,
            "max_completion_tokens": 50,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=3)
        if response.ok:
            questions_text = response.json()['choices'][0]['message']['content'].strip()
            # Clean and split the response
            questions = [q.strip().rstrip('?؟') for q in questions_text.split('|') if q.strip()]
            # Ensure we have valid questions
            questions = [q for q in questions if len(q.split()) <= 4 and len(q) > 0][:2]
            
            # If we don't have enough questions, provide defaults
            if len(questions) < 2:
                questions = ["احچيلي أكثر", "عندك مثال"]
                
            logger.info("Generated %s follow-up suggestions", len(questions))
            return questions
            
        logger.error("Follow-up API status=%s", response.status_code)
        return ["احچيلي أكثر", "عندك مثال"]
        
    except Exception as e:
        logger.error("Follow-up API failure: %s", type(e).__name__)
        return ["احچيلي أكثر", "عندك مثال"]

def generate_gpt_response(chat_history, new_question, is_followup=False):
    """Generates a GPT response to a question with enhanced context handling"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = "https://api.openai.com/v1/chat/completions"
    
    # Create a more informative system message based on whether this is a follow-up
    system_message = """You are Jamal (جمال), a warm, calm, thoughtful AI voice companion for an elderly blind Iraqi Arabic-speaking man in his late sixties. Your purpose is to support his independence, comfort, dignity, and everyday curiosity. Speak to him directly as a trusted conversational companion, never as a technical support bot.

LANGUAGE AND VOICE:
- Always answer in natural, familiar Iraqi Arabic (اللهجة العراقية), even if the request arrives in English or in imperfect transcription, unless he explicitly requests another language.
- Use clear, simple, spoken phrases suitable for listening rather than reading. Avoid formal newsreader Arabic, technical jargon, long lists, and unnecessary English.
- Be warm and respectful without exaggeration, excessive praise, or repetitive openings like 'أكيد' on every turn.
- Keep ordinary replies brief (roughly one to three short sentences), but expand when he asks for more detail, a story, or a thorough explanation. Do not end every reply with a question.

NATURAL CONVERSATION:
- Interpret the meaning behind imperfect, hesitant, colloquial, or self-corrected speech. If he changes his mind mid-sentence, follow his latest clear intention.
- Use the provided conversation history to understand references such as 'وباجر؟', 'ليش؟', and 'وبعدين شصار؟'. Do not unnecessarily repeat previous answers.
- If something is genuinely ambiguous, ask one simple clarification in Iraqi Arabic. Be patient with repetition and never make him feel at fault.
- He may wish to chat casually, ask about history, learn something, hear a story, or simply have company. Respond naturally and respectfully, without pretending to be human.

USEFULNESS AND TRUST:
- For questions about news, weather, time-sensitive events, or other current facts, do not fabricate real-time information or claim to have looked anything up unless such information was actually provided through available tools or context. Briefly explain limitations in plain Iraqi Arabic.
- For requests to call relatives, send messages, play music, or interact with a device, do not claim an action was performed unless an actual connected capability completed it. If unavailable, explain briefly and offer the closest genuinely available help.
- Because he is blind, avoid relying on visual instructions such as 'click here' or 'look at the screen'. Give practical spoken guidance when appropriate.
- If asked to describe his surroundings, make clear you cannot see them unless visual input is actually available; never invent objects or hazards.
- Treat family and private information respectfully. Do not assume conversations are shared with relatives or claim that anyone was notified.
- Be clear about uncertainty, prioritize safety, and recommend a trusted person for urgent hands-on assistance when needed.

Your replies are spoken aloud, so make each reply easy to understand on the first listen."""
    if is_followup:
        system_message += " This is a follow-up question to the previous conversation. Maintain context without repeating information already provided."
    
    messages = [{"role": "system", "content": system_message}]
    
    # Include relevant conversation history
    # For follow-ups, we include more context. For new questions, we limit to save tokens
    history_limit = 10 if not is_followup else 5
    for question, answer in chat_history[-history_limit:]:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    
    # Add the new question
    messages.append({"role": "user", "content": new_question})
    
    data = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": 300
    }
    
    try:
        # A bounded wait prevents an indefinitely blocked HTTP call. This is
        # not a guarantee of Alexa's overall response deadline.
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=(1, 5))
        response_data = response.json()
        if response.ok:
            response_text = response_data['choices'][0]['message']['content']
            
            # Generate follow-up questions for the response
            try:
                # Always try to generate follow-up questions
                followup_questions = generate_followup_questions(
                    chat_history + [(new_question, response_text)], 
                    new_question, 
                    response_text
                )
                logger.info("Follow-up suggestion count=%s", len(followup_questions))
            except Exception as e:
                logger.error("Follow-up failure: %s", type(e).__name__)
                followup_questions = []
            
            return response_text, followup_questions
        else:
            logger.error("OpenAI API status=%s", response.status_code)
            return "صار خلل بالاتصال. جرب تسألني مرة ثانية بعد شوي.", []
    except Exception as e:
        logger.error("OpenAI request failed: %s", type(e).__name__)
        return "صار خلل بالاتصال. جرب تسألني مرة ثانية بعد شوي.", []

class ClearContextIntentHandler(AbstractRequestHandler):
    """Handler for clearing conversation context."""
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("ClearContextIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []
        session_attr["last_context"] = None
        
        speak_output = "مسحت سياق حچينا بهالجلسة. كلي جمال، وبعدها سؤالك الجديد."
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class HelpIntentHandler(AbstractRequestHandler):
    """Explain the Arabic query format without calling the model."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return (handler_input.response_builder
                .speak("كلي جمال، وبعدها سؤالك. مثلا: جمال احچيلي عن تاريخ بغداد.")
                .ask("شنو تحب تسأل جمال؟")
                .response)


class FallbackIntentHandler(AbstractRequestHandler):
    """An unmatched intent is not a transcript; ask for a supported phrasing."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        return (handler_input.response_builder
                .speak("ما فهمت سؤالك زين. كلي جمال، وبعدها عيد سؤالك.")
                .ask("كلي مثلا: جمال احچيلي قصة.")
                .response)


class SessionEndedRequestHandler(AbstractRequestHandler):
    """A completed Alexa session must not produce more speech."""
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GptQueryIntentHandler())
sb.add_request_handler(ClearContextIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
