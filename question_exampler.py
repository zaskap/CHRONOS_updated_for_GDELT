import os
import json
import time
from tqdm import tqdm
import copy

from searcher import search
from reader import read_pages

from src.rewriter import rewrite_query
from src.questioner import ask_news_question
from src.timeline_generator import generate_timeline

from tilse.data.timelines import Timeline as TilseTimeline
from tilse.data.timelines import GroundTruth as TilseGroundTruth
from datetime import datetime
from evaluation import evaluate_dates

from news_keywords import TARGET_KEYWORDS


def save_json(data, file_path):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)



def generate(input_text, model, search_engine='bing', n_max_query=6, n_max_doc=30, freshness=''):
    news_timeline_all = {}
    if search_engine != 'bing':
        doc_list_all = search([input_text + ' timeline'], n_max_doc, search_engine)
    else:
        doc_list_all = search([input_text], n_max_doc, search_engine, freshness)
        print(n_max_doc,len(doc_list_all))

    if search_engine == 'bing':
        doc_list_all = read_pages(doc_list_all)
    
    for _ in range(10):
        question_list = []
        while question_list == []:
            question_list = ask_news_question(model=model, news=input_text, docs=doc_list_all, questions=question_list)  # question-based news background decomposition
            
        for question in question_list:
            queries = []
            # print(question)
            while queries == []:
                queries = rewrite_query(question, n_max_query, model=model)
                # if queries:
                    # print(queries)
                    
            if search_engine != 'bing':
                doc_list = search(queries, n_max_doc*2, search_engine) 
            else:
                doc_list = search(queries, n_max_doc*2, search_engine, freshness) 
            doc_list_curr_iter = []
            for d in doc_list:
                if d not in doc_list_all:
                    doc_list_curr_iter.append(d)
            
            if len(doc_list_curr_iter) == 0:
                continue
            tic = time.time()
            if search_engine == 'bing':
                doc_list_curr_iter = read_pages(doc_list_curr_iter[:6])
            print(len(doc_list), len(doc_list_all), len(doc_list_curr_iter), time.time() - tic)
            if len(doc_list_curr_iter) == 0:
                continue

    
            news_timeline = []
            gen_cnt = 0
            tic = time.time()
            while not news_timeline:
                news_timeline = generate_timeline(model=model, news=input_text, docs=doc_list_curr_iter[:6])    # generate timeline
                # print(news_timeline)
                if not news_timeline:
                    time.sleep(5)
                    gen_cnt += 1
                    print("Generating times: ", gen_cnt)
                if gen_cnt > 10:
                    break
            news_timeline_all[question] = news_timeline

    save_json(news_timeline_all, os.path.join(f'questions', f"{input_text.replace(' ', '_').replace('/', '')}.json"))
    return news_timeline_all



def evaluate(dataset, model='gpt-4o'):
    results = {}
    for keyword, query, index in tqdm(TARGET_KEYWORDS[dataset][:3] + TARGET_KEYWORDS[dataset][6:]):
        with open(f'data/{dataset}/{keyword}/timelines.jsonl', 'r') as f:
            gt_timelines = []
            for tl in f:
                tl = eval(tl.strip('\n'))
                if tl:
                    gt = {}
                    for ts, event in tl:
                        ts = ts.replace(' ', '')
                        if ts.count('-') == 2:
                            ts = datetime.strptime(ts, '%Y-%m-%dT00:00:00').date()
                        elif ts.count('-') == 1:
                            ts = datetime.strptime(ts, '%Y-%mT00:00:00').date()
                        else:
                            ts = datetime.strptime(ts, '%YT00:00:00').date()
                        gt[ts] = event
                    gt_timelines.append(gt)
        # Evaluate summarization
        ground_truth = TilseGroundTruth([TilseTimeline(g) for g in gt_timelines])
        num_dates = len(ground_truth.get_dates())
        
        begin_time = time.time()
        if 'open' not in dataset:
            predicts = generate(query, model, search_engine=f"{dataset} {keyword}")
        else:
            predicts = generate(query, model, freshness=keyword.split('_')[-1].replace('.', '-'))

        selections = []
        pred_timeline_all = {}
        best_f1 = 0
        best_timeline = {}
        for _ in range(5):
            best_question_tl = ('', '')
            for question, tls in predicts.items():
                pred_timeline = copy.deepcopy(pred_timeline_all)
                if question in selections:
                    continue
                for tl in tls:
                    try:
                        ts, event = tl['start'], tl['summary']
                        if ts.count('-') == 2:
                            ts = datetime.strptime(ts, '%Y-%m-%d').date()
                        elif ts.count('-') == 1:
                            ts = datetime.strptime(ts, '%Y-%m').date()
                        else:
                            ts = datetime.strptime(ts, '%Y').date()
                        if ts not in pred_timeline:
                            pred_timeline[ts] = [event]
                        else:
                            pred_timeline[ts].append(event)
                    except: # wrong timestamp format, discard it
                        pass
                try:
                    date_scores = evaluate_dates(TilseTimeline(pred_timeline), ground_truth)['f_score']
                except:
                    date_scores = 0

                if date_scores > best_f1:
                    best_question_tl = (tls, question)
                    best_timeline = copy.deepcopy(pred_timeline)
                    best_f1 = date_scores

            pred_timeline_all = copy.deepcopy(best_timeline)
            selections.append(best_question_tl[1])
        
        results[query] = selections
        print(selections, best_f1)

    return results

            


if __name__ == '__main__':
    examples = {}
    for dataset in [d for d in os.listdir('data') if os.path.isdir(os.path.join('data', d))]:
        exs = evaluate(dataset)
        for topic in exs:
            cnt = 1
            while topic+str(cnt) in examples.keys():
                cnt += 1

            if cnt == 1:
                examples[topic] = exs[topic]
            else:
                examples[topic+str(cnt)] = exs[topic]
    
    save_json(examples, 'data/question_examples.json')