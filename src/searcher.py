import os
import json
import requests
import concurrent.futures
import logging
from typing import Dict, List
# Added by Aswin
# Support for GDELT API
from gdeltdoc import GdeltDoc, Filters
import pandas as pd
from datetime import datetime
from pprint import pprint


def search(query_list: List[str], n_max_doc: int = 20, search_engine: str = 'bing', freshness: str = '', timespan: str = '') -> List[Dict[str, str]]:
    doc_lists = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(search_single, query, search_engine, freshness, timespan) for query in query_list]
        for future in concurrent.futures.as_completed(futures):
            try:
                doc_lists.append(future.result())
            except:
                pass
    doc_list = _rearrange_and_dedup([d for d in doc_lists if d])
    # return doc_list[:n_max_doc]
    return doc_list


def search_single(query: str, search_engine: str, freshness: str = '', timespan: str = '') -> List[Dict[str, str]]:
    try:
        if search_engine == 'gdelt':
            search_results = gdelt_request(query, timespan = timespan)
            # Internally formatted
            return search_results
        if search_engine == 'bing':
            search_results = bing_request(query, freshness=freshness)
            return bing_format_results(search_results)
        else:
            raise ValueError(f'Unsupported Search Engine: {search_engine}')
    except Exception as e:
        logging.error(f'Search failed: {str(e)}')
        raise ValueError(f'Search failed: {str(e)}')

def bing_request(query: str, count: int = 50, freshness: str = '') -> List[Dict[str, str]]:
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    headers = {'Ocp-Apim-Subscription-Key': BING_SEARCH_KEY}
    params = {'q': query, 'count': count, 'responseFilter': 'Webpages'}
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        web_pages = data.get('webPages', {}).get('value', [])
        return web_pages

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")  
    except Exception as err:
        print(f"An error occurred: {err}")  

    return []

def gdelt_request(query: str, count: int = 50, freshness: str = '', timespan = '3m') -> List[Dict[str, str]]:
    """
    Fetches news articles from the GDELT database based on the given search query and filters.

    Args:
        query (str): The search keyword to filter articles.
        count (int, optional): The number of articles to retrieve. Currently not used in filtering.
        freshness (str, optional): Unused parameter, possibly for future implementation.
        timespan (str, optional): The time range for searching articles, default is '3m' (last 3 months).

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing the extracted article details.
                              Each dictionary includes 'id', 'url', 'title', 'timestamp', 
                              'domain', 'language', and 'source_country'.
    """

    # Define filters for searching articles in GDELT
    f = Filters(
    keyword = query,
    timespan = timespan
    )

    # Initialize GDELT API client
    gd = GdeltDoc()

    # Search for articles matching the filters
    articles = gd.article_search(f)


    formatted_results = list()
    rank = 0
    for i, response_row in articles.iterrows():
        # Only process English-language articles
        if response_row["language"] is not None and response_row["language"] == "English":
            new_record =  {
                            # Ranking it in the order of occurrence, assumption that the order is 
                            'id': str(rank + 1)
                            ,'url': response_row["url"]
                            ,'title': response_row["title"]
                            ,'timestamp': datetime.fromisoformat(response_row["seendate"]).strftime('%Y-%m-%d %H:%M:%S')
                            ,'domain': response_row["domain"]
                            ,'language': response_row["language"]
                            ,'source_country': response_row["sourcecountry"]
                        }
            formatted_results.append(new_record)
            rank +=1
    
    # print(f"\n{''.join(['*']*40)}\nTotal english documents: {len(formatted_results)}\n{''.join(['*']*40)}\n")

    # print("\n\n\n\n\n")

    return formatted_results


def bing_format_results(search_results: List[Dict[str, str]]):
    formatted_results = [
        {
            'id': str(rank + 1),
            'title': str(res.get('name', '')),
            'snippet': str(res.get('snippet', '')),
            'url': str(res.get('url', '')),
            'timestamp': str(res.get('dateLastCrawled', ''))[:10]
        }
        for rank, res in enumerate(search_results)
    ]
    return formatted_results


def _rearrange_and_dedup(doc_lists: List[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    doc_list = []
    snippet_set = set()
    # print([len(i) for i in doc_lists])
    for i in range(50):
        for ds in doc_lists:
            if i < len(ds):
                if 'snippet' in ds[i]:
                    signature = ds[i]['snippet'].replace(' ', '')[:200]
                elif 'title' in ds[i]:
                    # Since in GDELT the snippet is not available, we use the title for signature
                    signature = ds[i]['title'].replace(' ', '')[:200]
                else:
                    signature = ds[i]['content'].replace(' ', '')[:200]
                if signature not in snippet_set:
                    doc_list.append(ds[i])
                    snippet_set.add(signature)
    return doc_list


if __name__ == '__main__':
    queries = ["figure ai"]
    search(queries, search_engine='gdelt', timespan='3m')