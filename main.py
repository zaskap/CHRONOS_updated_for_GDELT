import os
import argparse
import json
import time
import logging
from tqdm import tqdm

from src.searcher import search
from src.reader import read_pages

from src.questioner import ask_news_question, question_exampler
from src.rewriter import rewrite_query
from src.timeline_generator import generate_timeline, merge_timeline

from tilse.data.timelines import Timeline as TilseTimeline
from tilse.data.timelines import GroundTruth as TilseGroundTruth
from tilse.evaluation import rouge
from datetime import datetime
from evaluation import get_scores, evaluate_dates, get_average_results

from news_keywords import TARGET_KEYWORDS
from pprint import pprint
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--max_round', type=int, default=5, help='Rounds of Question')
# Added by Aswin
# Made gpt-3.5-turbo as default model instead of qwen2.5-72b-instruct
# This will be changed to an instruct class model once the complete solution is tested
parser.add_argument('--model_name', type=str, default='gpt-3.5-turbo', help='Model')
parser.add_argument('--dataset', type=str, choices=['open', 'crisis', 't17'], default='open', help='Dataset used')
parser.add_argument('--rewrite_baseline', action='store_true')
parser.add_argument('--question_exs', action='store_true')
parser.add_argument('--output', type=str, default='outputs')

args = parser.parse_args()
MAX_ROUNDS = args.max_round

def save_json(data, file_path):
    if args.rewrite_baseline:
        with open(file_path.replace('.json', '-rewrite.json'), 'w') as file:
            json.dump(data, file, indent=2, ensure_ascii=True)
    else:
        with open(file_path.replace('.json', '.json'), 'w') as file:
            json.dump(data, file, indent=2, ensure_ascii=True)

# Added by Aswin
# Making "gdelt" as default search engine and added timespan as an argument
def generate(input_text, model, num_dates=9999, search_engine='gdelt', n_max_query=6, n_max_doc=30, freshness='',timespan = ''):
    for _ in range(2):
        try:
            news_timeline = []
            news_timeline_all = []
            dates_all = set()
            
            ####### News Context Retrieval #######
            # Added by Aswin
            # Added support for gdelt search engine
            if search_engine == 'gdelt':
                doc_list_all = search(query_list = [input_text], search_engine = search_engine, timespan = timespan)
                doc_list_all = read_pages(doc_list_all, api='gpt')
            elif search_engine != 'bing':

                doc_list_all = search([input_text + ' timeline'], n_max_doc, search_engine)
            else:
                doc_list_all = search([input_text], n_max_doc, search_engine, freshness)
                doc_list_all = read_pages(doc_list_all)

            news_timeline = []
            gen_cnt = 0
            while not news_timeline:
                news_timeline = generate_timeline(model=model, news=input_text, docs=doc_list_all)    # generate timeline
                print(news_timeline)
                if not news_timeline:
                    time.sleep(5)
                    gen_cnt += 1
                    print("Generating times: ", gen_cnt)
                if gen_cnt > 5:
                    break
            news_timeline_all += news_timeline
            for ts in news_timeline:
                dates_all.add(ts['start'])
            print(f'Reference Timeline dates number: {num_dates}')
            print(f'Current Timeline dates number: {len(dates_all)}')

            
            ####### Iterative Self-Questioning #######
            question_list_all = []
            rewrite_time, search_time, generate_time, read_time = 0, 0, 0, 0
            if args.question_exs:
                question_examples = question_exampler(input_text, 3)
            else:
                question_examples = []
            for i in range(MAX_ROUNDS):
                tic0 = tic = time.time()
                question_list = []
                cnt = 0
                while question_list == []:
                    question_list = ask_news_question(model=model, news=input_text, docs=doc_list_all[-150:], questions=question_list_all, examples=question_examples)  # question-based news background decomposition
                    cnt += 1
                    if cnt > 10:
                        doc_list_all = doc_list_all[10:]
                        print('Stop generating new questions')
                        break
                question_time = time.time() - tic

                tic = time.time()
                query_list = {}
                queries = []
                print(f'Round {i} Question List: {question_list}')
                for question in question_list:
                    query_gen = []
                    print(question)
                    while query_gen == []:
                        query_gen = rewrite_query(question, n_max_query, model=model)
                        # query_gen = [question] # w/o rewrite
                        if query_gen:
                            print(query_gen)
                            query_list[question] = list(set(query_gen))
                            queries += query_gen
                        
                question_list_all += queries
                rewrite_time += time.time() - tic
                
                tic = time.time()
                # Added by Aswin
                # Added support for gdelt search engine
                if search_engine == 'gdelt':
                    doc_list = search(list(set(queries)), search_engine = search_engine, timespan = timespan)
                elif search_engine != 'bing':
                    doc_list = search(list(set(queries)), n_max_doc, search_engine) 
                else:
                    doc_list = search(list(set(queries)), n_max_doc, search_engine, freshness) 
                search_time += time.time() - tic

                doc_list_curr_iter = []
                for d in doc_list:
                    if d not in doc_list_curr_iter and d not in doc_list_all:
                        doc_list_curr_iter.append(d)
                doc_list_curr_iter = [d for d in doc_list_curr_iter]

                if search_engine == 'bing':
                    doc_list_curr_iter = read_pages(doc_list_curr_iter)
                    for doc in doc_list_curr_iter:
                        if doc['url'] in [d['url'] for d in doc_list_all]:
                            continue
                        if input_text.lower() in doc['title'].lower() or input_text.lower() in doc['snippet'].lower():
                            doc_list_all.append(doc)
                        else:
                            flag = True
                            for keyword in input_text.split(" "):
                                if keyword.lower() not in doc['title'].lower() and keyword.lower() not in doc['snippet'].lower():
                                    flag = False
                                    break
                            if flag:
                                doc_list_all.append(doc)
                # Added by Aswin
                # Added support for gdelt search engine
                elif search_engine == 'gdelt':
                    doc_list_curr_iter = read_pages(doc_list_curr_iter,api='gpt')
                    for doc in doc_list_curr_iter:
                        if doc['url'] in [d['url'] for d in doc_list_all]:
                            continue
                        if input_text.lower() in doc['title'].lower() or input_text.lower() in doc['content'].lower():
                            doc_list_all.append(doc)
                        else:
                            flag = True
                            for keyword in input_text.split(" "):
                                if keyword.lower() not in doc['title'].lower() and keyword.lower() not in doc['content'].lower():
                                    flag = False
                                    break
                            if flag:
                                doc_list_all.append(doc)
                else:
                    for doc in doc_list_curr_iter:
                        if doc not in doc_list_all:
                            doc_list_all.append(doc)
                
                # print(len(doc_list_all))

            
                news_timeline = []
                gen_cnt = 0
                tic = time.time()
                while not news_timeline:
                    news_timeline = generate_timeline(model=model, news=input_text, docs=doc_list_curr_iter)    # generate timeline
                    print(f"News Timeline: {news_timeline}")
                    if not news_timeline:
                        time.sleep(5)
                        gen_cnt += 1
                        print("Generating times: ", gen_cnt)
                    if gen_cnt > 5:
                        break
                news_timeline_all += news_timeline
                for ts in news_timeline:
                    dates_all.add(ts['start'])
                print(f'Reference Timeline dates number: {num_dates}')
                print(f'Current Timeline dates number: {len(dates_all)}')
                generate_time += time.time() - tic
            
            save_json(question_list_all + doc_list_all, os.path.join(f'{args.output}/docs', f"{input_text.replace(' ', '_').replace('/', '')}-{model}-{MAX_ROUNDS}.json"))

            news_timeline_all = sorted(news_timeline_all, key=lambda x: x['start'], reverse=True)
            
            return news_timeline_all
        
        except Exception as e:
            logging.warning(f'Error: {e}, retrying...')
            time.sleep(1)
    # Have added the save_json and return statement outside the loop to save the data even if the loop fails
    # TODO
    # Solve for following error
    # ERROR:root:Search failed: The query was not valid. The API error message was: Your query contained a phrase search that was too short or too long: How has Figure AI advanced AI-powered humanoid robots in various industries
    # Doc List: 0
    # WARNING:root:Error: list index out of range, retrying...
    
    # Potential causes: Some search APIs impose limits on the length of phrases enclosed in quotes, and it looks like your query exceeds that limit.
    save_json(question_list_all + doc_list_all, os.path.join(f'{args.output}/docs', f"{input_text.replace(' ', '_').replace('/', '')}-{model}-{MAX_ROUNDS}.json"))
            
    return news_timeline_all
    # Uncomment the following lines after figuring out the above mentioned error
    # logging.error('Failed generating response!')    
    # return []



# The evaluate() is not mandatory to generate timelines
# It is mainly used to assess the quality of generated timelines by comparing them to ground truth data.
# Hence for the current implementatin, I'm not using this function
# TODO
# Necessary changes to seach() parameters has to be made to make this function work properly and align with generate()
def evaluate(dataset, model='gpt-3.5-turbo'):
    metric = 'all'
    results = []
    overall_results = {}
    time_all = 0
    for keyword, query, index in tqdm(TARGET_KEYWORDS[dataset]):
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
        if dataset in ['crisis', 't17']:
            predicts = generate(query, model, num_dates=num_dates, search_engine=f"{dataset} {keyword}")
        else:
            predicts = generate(query, model, num_dates=num_dates, freshness=keyword.split('_')[-1].replace('.', '-'))
        time_all += time.time() - begin_time
        
        
        ####### Merge Timelines #######
        pred_timeline = {}
        for tl in predicts:
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
        
        sorted_pred_timeline = dict(sorted(pred_timeline.items(), key=lambda item: len(item[1]), reverse=True))
        
        if MAX_ROUNDS > 1:
            try:
                predicts = []
                predicts = merge_timeline(model=model, news=query, num_dates=num_dates, timelines=pred_timeline)
            except:
                pass
            print(predicts)

        if predicts:
            pred_timeline = {}
            for tl in predicts:
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
                
        if len(pred_timeline) != num_dates:
            all_dates = list(pred_timeline.keys())
            all_dates.sort(reverse=True)
            while len(pred_timeline) < num_dates and all_dates:
                date_to_add = all_dates.pop(0)
                if date_to_add not in pred_timeline:
                    pred_timeline[date_to_add] = sorted_pred_timeline[date_to_add]
                    

        save_timeline = []
        for s,e in pred_timeline.items():
           save_timeline.append({'start': s.strftime('%Y-%m-%d'), 'events': e})
        save_timeline = sorted(save_timeline, key=lambda x:x['start'])
        print(len(pred_timeline))
        pred_timeline = TilseTimeline(pred_timeline)

        evaluator = rouge.TimelineRougeEvaluator(measures=["rouge_1", "rouge_2"])
        try:
            rouge_scores = get_scores(metric, pred_timeline, ground_truth, evaluator)
            date_scores = evaluate_dates(pred_timeline, ground_truth)
            timeline_res = (rouge_scores, date_scores, pred_timeline)
            pprint(timeline_res)
            results.append(timeline_res)
            if keyword not in overall_results:
                overall_results[keyword] = {"rouge": rouge_scores, "date_score": date_scores, "predict-timeline": save_timeline}
                save_json(overall_results[keyword], os.path.join(f'{args.output}/timelines', f"{dataset}-{model}-{keyword}-{MAX_ROUNDS}.json"))
        except:
            print("=======Evaluation Error=======")
            pprint(save_timeline)

    avg_res = get_average_results(results)
    save_json({'res': avg_res, 'time': time_all / 3600}, os.path.join(args.output, f"{dataset}-{model}-{MAX_ROUNDS}-avg_score.json"))
    pprint(avg_res)
    return avg_res

if __name__ == '__main__':
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    if not os.path.exists(f'{args.output}/docs'):
        os.makedirs(f'{args.output}/docs')
    if not os.path.exists(f'{args.output}/timelines'):
        os.makedirs(f'{args.output}/timelines')

    # Executing the generate frunciton for the input text: "figure ai"
    # since I'm using to OpenAI API, I have set the time span to 6 months instead of 3 years as discussed.
    input_text = "figure ai"
    model = "gpt-3.5-turbo"
    search_engine='gdelt'
    timelines = generate(input_text = input_text, model = model, search_engine='gdelt',timespan = '6m')
    print(timelines)