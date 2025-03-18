from typing import Dict, List, Tuple
from .model import query_model
import traceback
import re

def generate_timeline(model: str, news: str, docs: list):
    input_length = 15000
    raw_prompt = _build_raw_prompt(news, docs, input_length=input_length)
    try:
        responses = query_model(model, raw_prompt)
        responses = responses.replace("'",'"').replace('"s ', "'s ")
        return post_process(responses)
    except Exception as e:
        print(f'Failed when generating timeline: {str(e)}')
        # Added by Aswin
        # Tracks the error better than just printing
        traceback.print_exc()
        return ''


def merge_timeline(model: str, news: str, num_dates: int, timelines: list):
    input_length = 15000
    raw_prompt = _build_raw_prompt_merge(news, num_dates, timelines)
    try:
        responses = query_model(model, raw_prompt)
        return post_process(responses)
    except Exception as e:
        print(responses)
        raise ValueError(f'Failed: {str(e)}') 


def _build_raw_prompt(news: str, docs: list, input_length: int = 30000) -> str:
    if len([d for d in docs]) > 0:
        if "snippet" in docs[0] and 'content' in docs[0]:
            if len([d for d in docs if d['snippet'] in d['content']]) > 0:
                max_length_per_doc = int(input_length / len([d for d in docs if d['snippet'] in d['content']]))
            else:
                max_length_per_doc = int(input_length / len([d for d in docs]))
        else:
            max_length_per_doc = int(input_length / len([d for d in docs]))
    else:
        max_length_per_doc = input_length

    raw_prompt = """<|im_start|>system\nYou are an experienced journalist building a timeline for the target news.\n\nCurrent news database: {docs}\n\n
    Instructions: 
    Step 1: Read each background news item and extract all significant milestone events related to the target news from your news database, along with their dates.
    Step 2: Write a description for each event, including key detail information about the event, using the phrasing from the news database as much as possible. Save all events as a list. The format should be: [{{"start": <date|format as "2023-02-02">, "summary": "<event description|no quotes allowed>"}}, ...] 

    Directly output your answer in the following format, as a list: 
    [{{"start": <date|format as "2023-02-02", cannot be empty, must include specific year, month, and day>, "summary": "<event description|no quotes allowed>"}}, ...] 
    ## example: [{{"start": "2023-02-02", "summary": "An event happens."}}]]
    <|im_end|>\n<|im_start|>user\nTarget News: {news}<|im_end|>\n<|im_start|>assistant\n"""

    if "snippet" in docs[0]:
        raw_prompt = raw_prompt.format(
            news=news,
            docs=''.join([f'\n"News {i}:\n  Title: {doc["title"]}\n  Publish_Time: {doc["timestamp"][:10]}\n  Content: {doc["content"][:max_length_per_doc]}"\n' if doc["snippet"] in doc["content"] else f'\n"News {i}:\n  Title: {doc["title"]}\n  Publish_Time: {doc["timestamp"][:10]}\n  Snippet: {doc["snippet"]}\n"\n' for i, doc in enumerate(docs, 1)])
        )
    else:
        raw_prompt = raw_prompt.format(
            news=news,
            docs=''.join([f'\n"News {i}:\n  Title: {doc["content"].split(chr(10))[0]}\n  Publish_Time: {doc["timestamp"][:10]}\n  Content: {chr(10).join(doc["content"].split(chr(10))[1:])[:max_length_per_doc]}"\n' for i, doc in enumerate(docs, 1)]).replace('Title: ""\n  ', '').replace("Title: ''\n  ", '')
        )

    print(len(raw_prompt))
    return raw_prompt


def _build_raw_prompt_merge(news: str, num_dates: int, timelines) -> str:
    raw_prompt = """<|im_start|>system\nYou are an experienced journalist building a timeline for the target news. \n\n Merge the existing news summaries and timelines in chronological order. 
    
    When merging the news summaries, select the top-{k} significant news from the original timeline, and strictly follow the chronological order from past to present without changing the original date, using "\n" to separate events that occurred on different dates. Directly output your answer in the following format: [{{"start": <date|format as "2023-02-02", cannot be empty, must include specific year, month, and day>, "summary": "<event description|no quotes allowed>"}}, ...]
    
    <|im_end|>\n<|im_start|>user\nTarget News: {news}\nOriginal Timeline: {timelines}<|im_end|>\n<|im_start|>assistant\n"""
    
    raw_prompt = raw_prompt.format(
        news=news,
        k=num_dates,
        timelines=timelines
    )
        
    return raw_prompt


def remove_extra_newlines(s):
    return re.sub(r'\n{2,}', ' ', s).replace(' \n\n', '\n\n')


def post_process(output):
    try:
        if '\n\n' in output:
            output = " ".join(output.split('\n\n')[1:-1])

        output = output.replace('"', "'").replace('\n', '')
        output = output.replace("{'", '{"').replace("'}", '"}').replace("': '", '": "').replace("', '", '", "')
        output = output.replace('"summary": ', '"summary": "').replace('"summary\': ', '"summary": "')
        output = output.replace('}, {"start"', '"}, {"start"').replace('}]', '"}]')
        output = eval(output.replace('""', '"'))
        assert isinstance(output, list) == True
    except:
        return ""
    return output


if __name__ == '__main__':
    from searcher import search
    from pprint import pprint

    queries = ["syria crisis"]
    docs = search(queries, search_engine='crisis syria', n_max_doc=20)
    pprint(generate_timeline('gpt-3.5-turbo', "syria crisis", docs))