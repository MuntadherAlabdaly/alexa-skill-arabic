# Jamal — Arabic routing and response patch

Prepared on October 9, 2026, from the Python code you provided, which is based on k4l1sh/alexa-gpt.

This is a focused patch kit for your existing Alexa skill, not an already-deployed skill or a complete GitHub import template. No remote repository, Alexa skill, account setting, or API credential was changed.

## Diagnosis

Your English interaction model declares GptQueryIntent with a slot named query. Your Arabic model declares only built-in intents and an invocation name, so it cannot route a question to the Python GptQueryIntentHandler. The Jamal prompt in your Python already instructs the model to reply in Iraqi Arabic.

Amazon's current slot reference lists AMAZON.SearchQuery for Arabic (SA). It is designed for broader phrases. AMAZON.Person is also available for Arabic but is designed for people's names, not general questions. The upstream tutorial's use of Person as an arbitrary-question collector should not be treated as a guarantee of reliable transcription.

SearchQuery intent samples must include a carrier phrase. The model here uses جمال, يا جمال, سؤالي, سؤالي هو, and أريد أسألك. It deliberately does not use a bare {query} sample. This baseline requires one of these phrases while the skill is listening; it does not establish always-on or unrestricted continuous dictation.

## Apply in your existing skill

1. Back up your existing code and models. In the Build tab select Arabic (SA), then open the JSON Editor. Paste ar-SA.json into that locale only. Keep your English model unchanged.
2. Save and Build Model; wait for the full build to finish. A JSON syntax check here is not an Amazon model-build result.
3. In Code, apply the changes in lambda_function.py, then save/deploy. All original function and class names/signatures are preserved. Restore your existing private server-side credential configuration: the downloadable full file contains YOUR_API_KEY, not your credential. The diff leaves the original credential assignment alone. Do not commit a real key to GitHub; wire secure secret storage before publishing a repository. This kit does not assume Alexa-hosted skills expose the same environment-variable controls as a Lambda function in your own AWS account.
4. In Test, choose Development, Arabic (SA), and enable Skill I/O. In the simulator type: افتحي مرحبا جمال. After launch, type: جمال احچيلي عن تاريخ بغداد. The query slot should contain the question after جمال. Test a follow-up with: جمال وضحلي أكثر.
5. Inspect request.locale, request.intent.name, and request.intent.slots.query.value. Expected: ar-SA, GptQueryIntent, and the Arabic question. Inspect response.outputSpeech too. Then test the same sequence by voice and on the actual device/app using the developer account and Arabic interaction language. App interface language alone is not proof that request.locale is ar-SA.

On an Alexa device the documented explicit launch pattern includes the wake word, for example: أليكسا، افتحي مرحبا جمال. In this patch جمال at the start of an in-skill question is a carrier phrase, not a custom wake word.

If Amazon's build rejects a type or sample, retain the exact error. Do not replace SearchQuery with a bare custom slot and assume that creates a universal Arabic transcript. Documentation support does not substitute for a successful build in your account.

## Reading the test result

- No invocation / no request reaching your skill: check launch, selected locale, development enablement, account, and endpoint configuration.
- AMAZON.FallbackIntent or an empty query: the question was not captured as intended; inspect the model and spoken phrasing. The fallback handler cannot recover an arbitrary transcript that is not in the request.
- GptQueryIntent with correct Arabic query, but an API error: investigate credentials, API access, connectivity, and latency.
- Correct Arabic outputSpeech but unsatisfactory speech: investigate the device's voice/language output and pronunciation separately from model instructions.

Do not use today's weather as the first acceptance test. The provided Python calls the language model but has no weather/news retrieval or calling/music tools. A limitation response about live weather is not evidence of an Arabic routing failure.

Alexa+ eligibility warnings are not diagnosed by these files. The missing Arabic model is an independently demonstrated bug; your Python contains no Alexa+ entitlement check. Any remaining app warning needs its exact wording and account/device context.

## Exact scope of the Python patch

Preserved:
- Every original class/function name and signature, including generate_gpt_response(), process_followup_question(), extract_context(), generate_followup_questions(), and lambda_handler.
- Your complete Jamal system prompt, byte-for-byte as a Python string.
- The main model identifier, chat-completions endpoint, payload token limit, and existing history-window/storage logic.
- The existing key variable/configuration approach; the distributed full file has a placeholder for safety.

Changed:
- Launch, reprompt, stop, reset and error speech are Arabic. Reset describes clearing the current session context, not erasing platform logs.
- The query handler checks missing/blank slots before using their values.
- Added HelpIntentHandler, FallbackIntentHandler, and SessionEndedRequestHandler; NavigateHome uses the existing stop handler.
- Kept generate_followup_questions() but disabled its extra model call by default using ENABLE_FOLLOWUP_SUGGESTIONS = False. Its optional prompts/default phrases are Arabic when re-enabled. Re-enabling this adds an extra model request and has not been tested against a live API.
- Escaped generated text before embedding it in Alexa's speech markup.
- Added an HTTP connect/read timeout to the main request. This is not a hard deadline for the entire Alexa response.
- Removed verbatim API errors from spoken output and limited diagnostic logs to routing/status metadata instead of generated follow-up content.

The Arabic model also declares ClearContextIntent, which your Python already implemented but your earlier schemas did not include.

## Local validation — not deployment verification

Python syntax was compiled successfully. Both JSON files parse. The source comparison verified that all 14 original callable signatures and the complete Jamal prompt are preserved. Fifteen offline tests passed for query forwarding, missing slots, intent coverage, help/fallback/stop/reset/session end, output escaping, API-error handling, and the default no-extra-follow-up-call behavior.

These tests stub the ASK SDK and HTTP. The SDK was not available in the working environment, and its package download was unavailable. Tests do not validate actual SDK serialization, Amazon's model build, live OpenAI access, Alexa+ eligibility, device audio, or Iraqi-dialect recognition. No real credentials or live OpenAI requests were used.

Run the logic checks with:

```bash
python test_logic.py
python -m py_compile lambda_function.py
```

Keep your current deployment requirements when applying the patch. requirements.txt records the existing tutorial's ASK SDK version and requests dependency; it is not a new dependency upgrade recommendation.

## Files

- ar-SA.json: Arabic model to paste into the Arabic locale's JSON Editor.
- lambda_function.py: your Python implementation with the documented patch and a credential placeholder.
- arabic_changes.patch: a credential-free diff for review/application from the directory containing lambda_function.py.
- en-US.original.json: your pasted English model preserved for reference; this is not a substitute for backing up the actual console version.
- test_logic.py / test_results.txt: offline tests and their observed result.
- LICENSE: upstream MIT license.

## Primary sources checked

- Amazon — Develop Skills in Multiple Languages: https://developer.amazon.com/en-US/docs/alexa/custom-skills/develop-skills-in-multiple-languages.html
- Amazon — Slot Type Reference (Arabic support, Person and SearchQuery): https://developer.amazon.com/en-US/docs/alexa/custom-skills/slot-type-reference.html
- Amazon — Tips for Using Built-in Slots: https://developer.amazon.com/en-US/docs/alexa/interaction-model-design/tips-for-using-built-in-slots-for-your-skill.html
- Amazon — Test Skills in the Alexa Developer Console: https://developer.amazon.com/en-US/docs/alexa/devconsole/test-your-skill.html
- Amazon — How Users Invoke Custom Skills: https://developer.amazon.com/en-US/docs/alexa/custom-skills/understanding-how-users-invoke-custom-skills.html
- Upstream repository: https://github.com/k4l1sh/alexa-gpt
- OpenAI — API Key Safety: https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety
