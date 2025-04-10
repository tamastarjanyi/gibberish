import logging
from threading import Lock

import httpx
from openai import OpenAI


class TextVerifier:
    # is_grammatically_correct_prompt = 'You are a language expert analyzing LLM responses. Analyze the below LLM response and if it is a grammatically correct text response with only [YES] otherwise response with only [NO]. Analyze only the grammar but do not analyze the context and the content.'
    is_grammatically_correct_prompt = 'Act like a language expert with expertise in grammar analysis.\nAnalyze the below LLM response and if it is a grammatically correct text response with only YES otherwise response with only NO. Analyze only the grammar but do not analyze the context and the content.'
    client: OpenAI = None
    lock: Lock = Lock()

    def __init__(self, endpoint: str,
                 x_api_key: str, model_name: str):
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.info(f"Initializing {self.__class__.__name__}...")
        self.endpoint = endpoint
        self.model_name = model_name
        self.x_api_key = x_api_key
        _hc = httpx.Client(verify=False)
        _headers = {"X-API-Key": x_api_key}
        with TextVerifier.lock as l:
            self.logger.info("Createing openai client...")
            if not self.client:
                TextVerifier.client = OpenAI(default_headers=_headers, base_url=endpoint, api_key=x_api_key,
                                             http_client=_hc)

    def is_grammatically_correct(self, text: str, temperature: float = 0.2) -> (bool, str):
        messages = [{"role": "system", "content": TextVerifier.is_grammatically_correct_prompt},
                    {"role": "user", "content": text}]
        # prompt = f"{TextVerifier.is_grammatically_correct_prompt}\n\n\n{text}"
        # messages = [{"role": "user", "content": prompt}]
        completion = TextVerifier.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=10,
            stream=False,
            stop=[],
        )
        c = completion.choices[0].message.content
        if c.lower().strip() in ["[yes]", "yes"]:
            return (True, c)
        else:
            return (False, c)
