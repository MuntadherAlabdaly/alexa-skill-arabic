# Jamal — Alexa skill

Jamal is an Alexa-hosted Python skill that answers in familiar Iraqi Arabic. This repository uses Amazon's supported skill-package layout and can be imported directly from its public Git URL.

## Repository structure

```text
.
├── lambda/
│   ├── lambda_function.py
│   └── requirements.txt
├── skill-package/
│   ├── skill.json
│   └── interactionModels/
│       └── custom/
│           ├── ar-SA.json
│           └── en-US.json
├── tests/
│   └── test_logic.py
├── docs/
│   ├── arabic_changes.patch
│   └── test_results.txt
├── LICENSE
└── .gitignore
```

## Import into Alexa

1. In the Alexa Developer Console, create a **Custom** skill.
2. Choose **Arabic (SA)** as the default language.
3. Choose **Alexa-Hosted (Python)** for the backend.
4. Select **Import skill** and enter:

   `https://github.com/MuntadherAlabdaly/alexa-skill-arabic.git`

5. Review the invocation name, build the interaction model, configure the private OpenAI credential, and deploy.

The invocation-name warning is separate from the repository package format and may still need to be resolved in the Alexa Developer Console.

## Credentials

`lambda/lambda_function.py` contains the placeholder `YOUR_API_KEY`. Do not commit a real credential to this public repository. Configure the credential privately before deployment.

## Local validation

```bash
python tests/test_logic.py
python -m py_compile lambda/lambda_function.py
python -m json.tool skill-package/skill.json >/dev/null
python -m json.tool skill-package/interactionModels/custom/ar-SA.json >/dev/null
python -m json.tool skill-package/interactionModels/custom/en-US.json >/dev/null
```

The offline tests stub the Alexa SDK and HTTP calls. They do not replace an Alexa model build or a live import test in your Amazon account.
