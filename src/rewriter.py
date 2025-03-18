from typing import List
from .model import query_model

def rewrite_query(query: str, n_max_query: int = 5, model: str = 'gpt-4o') -> List[str]:
    raw_prompt = _build_raw_prompt(query)
    while True:
        try:
            responses = query_model(model, raw_prompt)
            if "lama" not in model:
                queries = _parse_output(responses)
            else:
                
                if '\n\n' in responses:
                    if responses.count('\n\n') == 1:
                        response = "".join(responses.split('\n\n')[1])
                    else:
                        response = "".join(responses.split('\n\n')[1:-1])
                if '\n' in response:
                    responses = [eval(d.lstrip('1.' ).lstrip('2.' ).lstrip('3.' ).lstrip('4.' ).lstrip('5.' )) for d in response.split('\n')]
                    queries = []
                    for res in responses:
                        queries += res
                
            return queries[:n_max_query]
        except Exception as e:
            print(f'Failed when rewriting query: {str(e)}')
            return []

def _build_raw_prompt(query: str) -> str:
    raw_prompt = f"""<|im_start|>system\nGenerate 2-3 English rewrite queries of the user query as a python list, directly output it as ["..", "..", ".."]
    ## Example:
    <|im_start|>user\nWhen did the initial protests that led to the Egyptian Crisis begin?<|im_end|>\n<|im_start|>assistant\n["Egyptian Crisis initial protests", "Time of protests lead to Egyptian Crisis"]<|im_end|>
    <|im_start|>user\nWhen and where did Robert Jasmiden die?<|im_end|>\n<|im_start|>assistant\n["Robert Jasmiden's death time", "Robert Jasmiden's death place"]<|im_end|>
    <|im_start|>user\nWhat profession do Nicholas Ray and Elia Kazan have in common?<|im_end|>\n<|im_start|>assistant\n["Nicholas Ray profession", "Elia Kazan profession"]<|im_end|>
    <|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n"""
    return raw_prompt


def _parse_output(output: str) -> List[str]:
    # results = re.findall('\'(.*?)\'', output)
    results = eval(output)
    return results



if __name__ == '__main__':
    print(rewrite_query('What actions were suggested by the White House in response to the collapse of Silicon Valley Bank and Signature Bank'))
