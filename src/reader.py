import os
import uuid
import time
import json
import re
import requests
from bs4 import BeautifulSoup
import concurrent.futures
import logging
from typing import Dict, List
from copy import copy

# Have use Langchain pipline to extract the relevant content from the given url
from langchain.prompts.prompt import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser



JINA_API_KEY = "JINA_API_KEY"
OPENAI_API_KEY = "OPENAI_API_KEY"

def read_pages(docs: List[Dict[str, str]], api='jina') ->List[Dict[str, str]]:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(read_page, doc, api) for doc in docs]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except:
                pass
    return results


def read_page(doc: Dict[str, str], api='damo') -> Dict[str, str]:
    assert doc.get('url', '') != ''
    for _ in range(2):
        try:
            if api == 'jina':
                doc['content'] = read_page_jina(doc['url'])
            # Added by Aswin
            # Support for GPT-3.5 Langchain pipeline based content extraction
            elif api == 'gpt':
                doc['content'] = read_page_gpt(doc['url'], title = doc['title'])
            else:
                raise ValueError(f'Unknown Readpage API: {api}')
            return doc
        except Exception as e:
            logging.warning(f'Readpage failed: {str(e)}, retrying')
            time.sleep(1)

    raise ValueError(f'Readpage failed')

def extract_url_content_in_human_readable_format(url: str) -> str:
    """
    Fetches the webpage content from the given URL, removes unnecessary elements like scripts and styles, 
    and extracts human-readable text.

    Args:
        url (str): The URL of the webpage to fetch.

    Returns:
        str: Extracted text from the webpage in human-readable format, or an error message if the fetch fails.
    """
    try:
        # Fetch webpage content
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise error for failed requests
        
        # Parse HTML and extract text and remove scripts and style elements as they do not contain meaningful content
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):  # Remove unnecessary elements
            script.extract()
        
        # Get the visible text from the HTML document
        text = soup.get_text(separator="\n", strip=True)
        
        return text

    except Exception as e:
        return f"Error fetching or summarizing webpage: {str(e)}"


def read_page_gpt(url: str, title: str) -> str:
    """
    Extracts relevant content from a webpage using GPT-3.5-turbo after pre-processing the content with BeautifulSoup.

    Args:
        url (str): The URL of the webpage to extract content from.
        title (str): The title of the content to be extracted.

    Returns:
        str: Extracted content relevant to the given title, cleaned from unnecessary elements.
    """

    # Have used custom prompt to extract the relevant content from the given url
    # Statement 6 was made to resolve an unicode error encounterd while writing the extracted content to the json file in main.py
    summary_template = """
            The following information {information} has the title {title}. 
            After processing with Beautiful Soup to get human readable format, the given content has lot of 
            unnecessary information apart from the title and original content.
            I want you to extrat the relevant content associated with the title using the given hints
                1. The content should be assiciated with given title
                2. The unnecessary text has lot of newline charcter("\n") in vicinity.
                3. DO NOT summarize the content.
                4. DO NOT skip any important events and their associated dates.
                5. No URLs should be present in the extracted content.
                6. Make sure that only ASCII characters are present in the extracted content.
            """
    # Initalize the Prompt Template for the LLM
    summary_prompt_template = PromptTemplate(
        input_variables=["url", "title"], template=summary_template
    )
    # Initialize the LLM model
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo", api_key = OPENAI_API_KEY)
    # llm = ChatOllama(temperature=0, model="llama3.2")

    # Chain of Actions
    chain = summary_prompt_template | llm | StrOutputParser()

    information = extract_url_content_in_human_readable_format(url)

    extracted_content =  chain.invoke(input={"information": information, "title":title})
    extracted_content

    return extracted_content

 
def read_page_jina(url: str) -> str:
    headers = {
        'Authorization': f'Bearer {JINA_API_KEY}',
        'X-Timeout': 5,
        'Accept': 'application/json',
        'X-Return-Format': 'text'
    }

    resp = requests.get(f'https://r.jina.ai/{url}')

    if resp.status_code != 200:
        raise Exception(f'Error: {resp.status_code} {resp.text}')
    
    content = resp.text

    try:
        prefix = 'Markdown Content:\n'
        content = content[content.index(prefix)+len(prefix):]
    except:
        pass
    content = re.sub('\[(.+?)\]\(.+?\)', '[\\1]', content)

    return content



if __name__ == '__main__':
    print(read_pages([{'url': 'https://www.pbs.org/newshour/search-results?q=a+timeline+of&pnb=1'}]))
