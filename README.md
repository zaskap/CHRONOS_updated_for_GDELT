# CHRONOS_updated_for_GDELT
This is an adaptation of CHRONOS: Repo for NAACL 2025 Paper "Unfolding the Headline: Iterative Self-Questioning for News Retrieval and Timeline Summarization" and enhance it with GDELT search engine capabilities


# Features Implemented:
* Search operation with GDELT compatibility (src/searcher.py)
* Langchain pipeline to extract the url content in human readable format. I have used gpt-3.5-turbo as the LLM model with a custom prompt template for this (src/reader.py)
* Compatibility for GDELT based search without obstructing existing functionality (main.py)
* Some relevant modifications wherever required to execute the code successfully
* Requirement.txt has been updated with relevant libraries along with pytorch installation options
* Some erroes on due to usage of deprecated funcitons of OpenAI are resolved (src/model.py) 


# Scope for Improvement:
* Environment file for API keys to enable common access across the code files
* The event timeline output is non-deterministic. With different executions, the output need not be same. Need to make it deterministic.
* Streamlit based UI for users to select relevant models and search engines to explore various search strings like “figure ai”
* Quantify the outputs using evaluation() function. (possibly to explore options for the search strings without groundtruths)
* Investigate certain types of error arising due to the limitations of API
  * ERROR:root:Search failed: The query was not valid. The API error message was: Your query contained a phrase search that was too short or too long: How has Figure AI advanced AI-powered humanoid robots in various industries
  * WARNING:root:Error: list index out of range, retrying...
 
# How to Use
* Create a new python virtual environment
* Install the packages from requirements.txt - `pip install -r requirements.txt`
* Use the IDE of your choice to explore the code
* Make sure the configure your API Keys for OPENAI and other services as required
* Run main.py

# Citation
@article{wu2025unfoldingheadlineiterativeselfquestioning,
      title={Unfolding the Headline: Iterative Self-Questioning for News Retrieval and Timeline Summarization}, 
      author={Weiqi Wu and Shen Huang and Yong Jiang and Pengjun Xie and Fei Huang and Hai Zhao},
      year={2025},
      eprint={2501.00888},
      archivePrefix={arXiv},
      primaryClass={cs.CL},
      url={https://arxiv.org/abs/2501.00888}, 
}

