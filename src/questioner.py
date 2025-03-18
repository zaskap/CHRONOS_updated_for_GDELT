import os
from typing import Dict, List, Tuple
import requests
import json
from transformers import BertModel, BertTokenizer

from sklearn.metrics.pairwise import cosine_similarity
from .model import query_model


with open('data/question_examples.json') as f:
    example_pool = json.load(f)

tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertModel.from_pretrained('bert-base-uncased')


def get_bert_vector(text):
    inputs = tokenizer(text, return_tensors='pt')
    outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).squeeze().detach().numpy()


def question_exampler(news, k):
    candidates = [n for n in example_pool.keys() if news not in n]
    news_vector = get_bert_vector(news)
    candidate_vectors = [get_bert_vector(c) for c in candidates]
    scores = cosine_similarity([news_vector], candidate_vectors).flatten()
    ranked_examples = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    ranked_examples = ranked_examples[:k]
    print(ranked_examples)
    return [[exs[0], example_pool[exs[0]]] for exs in ranked_examples]


def question_exampler_random(news, k):
    import random
    candidates = [n for n in example_pool.keys() if news not in n]
    ranked_examples = random.sample(candidates, k)
    return [[exs, example_pool[exs]] for exs in ranked_examples]


def ask_news_question(model: str, news: str, docs: list = [], questions: list = [], examples: list = []):
    input_length = 15000
    raw_prompt = _build_raw_prompt(news, docs, questions, input_length=input_length, examples=examples)
    try:
        responses = query_model(model, raw_prompt)
        if '\n\n' in responses:
            responses = '\n'.join(responses.split('\n\n')[1:-1])
            responses = str([d.lstrip('1.' ).lstrip('2.' ).lstrip('3.' ).lstrip('4.' ).lstrip('5.' ) for d in responses.split('\n')])
        return eval(responses)
    except Exception as e:
        try:
            return eval(responses.replace("\'s", ""))
        except Exception as e:
            print(f'Failed when generating questions: {str(e)}') 
            return []


def _build_raw_prompt(news: str, docs: list = [], questions: list = [], input_length: int = 30000, examples: list = []) -> str:
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

    raw_prompt = """<|im_start|>system\nYou are an experienced journalist building a timeline for the target news or entity. \nCurrent News Database:{docs}\n\nYou need to propose at least 5 questions related to the Target News that the current news database cannot answer. These questions should help continue organizing the timeline of news developments or the life history of individuals, focusing on the origins, development processes, and key figures of related events, emphasizing factual news knowledge rather than subjective evaluative content. These 5 questions must be independent and non-overlapping The overall potential information volume of all questions should be as large as possible, and the time span covered should also be as extensive as possible. Avoid asking questions similar to those already searched. Directly output your questions in the specified format.\n\n##Output format: ["Question 1", "Question 2", "Question 3", ...]<|im_end|>\n<|im_start|>user\nTarget News:{news}\n\nQuestions Already Searched:{questions}<|im_end|>\n<|im_start|>assistant\n"""

    if "snippet" in docs[0]:
        if "content" in docs[0]:
            raw_prompt = raw_prompt.format(
                news=news,
                docs=''.join([f'\n"News {i}:\n  Title: {doc["title"]}\n  Publish_Time: {doc["timestamp"][:10]}\n  Content: {doc["content"][:max_length_per_doc]}\n' for i, doc in enumerate(docs, 1)]),
                questions=questions
            )
        else:
            raw_prompt = raw_prompt.format(
                news=news,
                docs=''.join([f'\n"News {i}:\n  Title: {doc["title"]}\n  Publish_Time: {doc["timestamp"][:10]}\n  Snippet: {doc["snippet"]}\n"\n' for i, doc in enumerate(docs, 1)]),
                questions=questions
            )
    else:
        raw_prompt = raw_prompt.format(
            news=news,
            docs=''.join([f'\n"News {i}:\n  Title: {doc["content"].split(chr(10))[0]}\n  Publish_Time: {doc["timestamp"][:10]}\n  Content: {chr(10).join(doc["content"].split(chr(10))[1:])[:max_length_per_doc]}"\n' for i, doc in enumerate(docs, 1)]).replace('Title: ""\n  ', '').replace("Title: ''\n  ", ''),
            questions=questions
        )

    examples_str = ""
    for exs in examples:
        examples_str += f"\n<|im_start|>user\nTarget News: {exs[0]}\n<|im_start|>assistant\n{exs[1]}"
    
    raw_prompt = raw_prompt.replace('##Output format: ["Question 1", "Question 2", "Question 3", ...]', '##Output format: ["Question 1", "Question 2", "Question 3", ...]\n\n##Examples: '+ examples_str)
    
    return raw_prompt


if __name__ == '__main__':
    from searcher import search
    from pprint import pprint
    pprint(ask_news_question('gpt-3.5-turbo', "egypt crisis", docs=search(['egypt crisis'], search_engine='crisis egypt')))
