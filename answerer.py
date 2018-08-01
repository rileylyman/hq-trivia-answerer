import requests
import threading
import time
from bs4 import BeautifulSoup

SEARCH_TIME: float = 8.0

def get_links(query : str) -> list:
    page = requests.get("https://www.google.com/search?q="+query)
    soup = BeautifulSoup(page.content, features="html.parser")
    return [link["href"][7:] for link in soup.findAll("a") if link["href"][:7] == "/url?q="]

def get_mention_counts(links: list, phrases: list) -> str:
    all_valid_counts = []
    threads = []

    phrases_to_search : dict = valid_phrases(phrases)

    for phrase in phrases_to_search.keys():
        thread = threading.Thread(target=lambda links, phrase:\
            all_valid_counts.append((phrase, search_in_text(links, phrase))),
            args=(links, phrase))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()

    mention_counts = {phrase : 0 for phrase in phrases}
    for x, count in all_valid_counts:
        mention_counts[phrases_to_search[x]] += count
    return mention_counts.items()

def search_in_text(links: list, phrase: str) -> int:    
    counts = []
    search_threads = []
    timeout_cap = SEARCH_TIME / len(links)
    for link in links:
        current_thread = threading.Thread(target=count_phrase, args=(link, phrase, counts))
        current_thread.start()
        search_threads.append(current_thread)
    for thread in search_threads:
        thread.join(timeout=timeout_cap)
    return sum(counts)   
    
def count_phrase(link : str, phrase: str, phrase_counts : list):
    try:
        page = requests.get(link)
        count = page.text.lower().count(phrase)
        phrase_counts.append (count)
    except:
        pass

def valid_phrases(choices: list) -> list:
    valids = []
    nouns = []
    for phrase in choices:
        valids.append(phrase)
        #tokenize phrase
    return {choice:choice for choice in choices}

 
def evaluate_results(list_of_counts: list):
    #rough sketch
    answer = list_of_counts[0][0][0]
    confidence = 0.0

    total_count = sum([kv[1] for phrase_counts in list_of_counts for kv in phrase_counts])
    if total_count == 0: 
        return (answer, confidence)
    
    for phrase_counts in list_of_counts:
        sorted_counts = sorted(phrase_counts, key=lambda kv: kv[1], reverse=True)
        current_confidence = float(sorted_counts[0][1]) / total_count
        for i in range(1, len(sorted_counts)):
            current_confidence -= float(sorted_counts[i][1]) / total_count
        if current_confidence > confidence:
            confidence = current_confidence
            answer = sorted_counts[0][0]

    return (answer, confidence)

def run(question: str, choices: list, counts: list) -> str:
    links = get_links(question)
    counts.extend(get_mention_counts(links, choices))
    
def add_choices_to_question(question : str, choices: list) -> str:
    for choice in choices:
        question += " " + choice
        #deal with choice types that could be recognized under different circumstances
        if len(choice) > 0 and choice[-1] == 's': 
            question += " " + choice[:-1]
    return question

def clean_choices(choices: list):
    for i in range(len(choices)):
        choices[i] = choices[i].lower()
 
def answer(question : str, choices: list) -> str:
    start_time = time.time()    
    
    clean_choices(choices)

    normal_counts, modified_counts = [], []
    normal_thread = threading.Thread(target=(lambda q,c,cs: run(q,c,cs)), args=(question, choices, normal_counts))
    modified_thread = threading.Thread(target=(lambda q,c,cs: run(q,c,cs)),\
                                       args=(add_choices_to_question(question, choices), choices, modified_counts))
    normal_thread.start()
    modified_thread.start()
    normal_thread.join()
    modified_thread.join()

    answer, confidence = evaluate_results([normal_counts, modified_counts])

    print ("\n")
    print ("Web scraping results: \n\t" + "Original pass: " + str(normal_counts) + "\n\tUpdated pass: " \
               + str(modified_counts))
    print ("Confidence: " + str(confidence) + " for result of " + answer)
    print ("Time elapsed: " + str(time.time() - start_time))
    return answer
