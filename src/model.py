import dashscope
from http import HTTPStatus
from openai import OpenAI
import json


DASHSCOPE_API_KEY = "YOUR_API_KEY"
OPENAI_API_KEY = "YOUR_API_KEY"
client = OpenAI(api_key=OPENAI_API_KEY)


def query_model(model: str, raw_prompt: str):
    if 'qwen' in model:
        responses = query_qwen(model, raw_prompt)
    elif 'gpt' in model:
        responses = query_gpt(model, raw_prompt)
    return responses


def query_qwen(model: str, raw_prompt: str):
    response = dashscope.Generation.call(
        api_key=DASHSCOPE_API_KEY,
        model=model,
        prompt=raw_prompt,
        result_format='message',
        use_raw_prompt=True
    )
    if response.status_code == HTTPStatus.OK:
        return response.output.choices[0].message.content
    else:
        err = 'Error code: %s, error message: %s' % (
            response.code,
            response.message,
        )
        return err


def query_gpt(model: str, raw_prompt: str):
    response = client.chat.completions.create(
        model=model, 
        # The underlying line was not aligne with the OpenAI API documentation starndard. The messages have to be a list of dictionaries.
        messages=[{"role": "user", "content": raw_prompt}]
    )
    # content is not a key in the response object. It is an attribute.
    return response.choices[0].message.content