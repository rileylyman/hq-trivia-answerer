import nltk
import time
import json
import requests
from secrets import CX, API

class Question(object):

    _url = 'https://www.googleapis.com/customsearch/v1'
    _headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}
    _cx = CX
    _api = API
    
    def __init__(self, question: str, choices: list, autorun=False):
        self.question = question
        self.choices = self._clean(choices)
        self.search_phrases: dict = self._to_search()
        self.choice_counts = dict( [ (choice, 0) for choice in choices ] )

        self.start_time = time.time()
        self.confidence: float = 0.0
        self.guess = choices[0]

        self._iteration = 1

        self.links, self.splash_text = self._get_links()
        if autorun:
            self.answer()

    def answer(self): # prints its best guess for multiple web scrapes
        self._analyze_splash()
        for link in self.links:
            self._iteration += 1
            self._analyze_link(link)
        return self.guess

    def _analyze_splash(self):
        self._analyze_text(self.splash_text)

    def _analyze_link(self, link:str):
        page = self._make_request(link)
        text = str(page.content)
        self._analyze_text(text)

    def _analyze_text(self, text:str):
        for choice in self.search_phrases.keys():
            self.choice_counts[self.search_phrases[choice]] += text.count(choice)
        self._evaluate()

    def _evaluate(self):
        self._update_confidence()
        if (self._iteration == 1):
            print('shallow iteration')
        else:
            print('iteration', self._iteration, 'of', len(self.links) + 1)
        print('confidence:', self.confidence)
        print('current duration:', time.time() - self.start_time)
        print('============================= best guess:', self.guess)

    def _update_confidence(self):
        total_count = sum(self.choice_counts.values())
        if total_count > 0:
            sorted_counts = sorted(self.choice_counts.keys(), 
                            key=lambda choice: self.choice_counts[choice], reverse=True)

            current_confidence = float(self.choice_counts[sorted_counts[0]]) / total_count
            for i in range(1, len(sorted_counts)):
                current_confidence -= float(self.choice_counts[sorted_counts[i]]) / total_count 

            self.confidence = current_confidence
            self.guess = sorted_counts[0]      

    def _get_links(self) -> tuple: # returns (list<links>, text)        
        page  = self._make_request(self._url, params=self._params())
        json_data = json.loads(page.content)

        links = [item['link'] for item in json_data['items']]
        text = ''.join([
            item['title'] + item ['htmlTitle'] + item['snippet'] + item['htmlSnippet']
            for item in json_data['items']
        ])       
        return (links, text.lower())

    def _make_request(self, url:str, params:dict = {}):
        return requests.get(url, params=params, headers=self._headers)

    def _to_search(self) -> list: # returns search words associated with their phrase
        valids = []
        for phrase in self.choices:
            valids.append((phrase, phrase))
            if len(phrase.split()) > 1:
                tokenized_phrase = nltk.pos_tag(nltk.word_tokenize(phrase))
                valids.extend([(token, phrase) for token, tag in tokenized_phrase
                                if tag[:2] == 'NN' and token != phrase])
        return dict(valids)
    
    def _modified_question(self) -> str:
        for choice in self.choices:
            question += ' ' + choice
        return question

    def _clean(self, choices: list) -> list:
        for i in range(len(choices)):
            choices[i] = choices[i].lower()
        return choices

    def _params(self) -> dict:
        return {
            'q':self.question,
            'cx':self._cx,
            'key':self._api
        } 
