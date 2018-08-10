import nltk
import time
import json
import requests
import threading
from bs4 import BeautifulSoup
from bs4.element import Comment
from secrets import CX, API

#remember to add in augmented questions
class Question(object):

    _url = 'https://www.googleapis.com/customsearch/v1'
    _headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}
    _cx = CX
    _api = API

    RVF = 10
    
    def __init__(self, question: str, choices: list, autorun=False, nlp=None):
        self.start_time = time.time()
        
        if not nlp:
            #You should always remember to call nlp.close() if you call __init__ but 
            #do not call self.answer(), otherwise, the nlp server will continue to run
            #Also, not providing nlp will cause _get_root_verb to run too slowly the first
            #time, so in practice nlp should always be instantiated and tested before
            #using the answerer to ensure answers within the time limit
            self.stanford_nlp = self.create_nlp()
        else:
            self.stanford_nlp = nlp

        self.question = question
        self.root_verb, self.is_negated = self._get_root_verb(question)
        self.choices = self._clean_choices(choices)
        self.search_phrases: dict = self._to_search()
        self.choice_counts = dict( [ (choice, 0) for choice in choices ] )

        self.confidence: float = 0.0
        self.guess = choices[0]

        self.guess_stats = {}

        self._iteration = 1

        self.links, self.splash_text = self._get_links()
        self.all_text = self.splash_text
        if autorun:
            self.answer()

#################################################################################
#The main loop

    def answer(self, close=True): # prints its best guess for multiple web scrapes
        self._analyze_splash()
        for link in self.links:
            self._iteration += 1
            self._analyze_link(link)
        if close:
            self.stanford_nlp.close()
        print (self.choice_counts)
        return self.guess

    def _analyze_splash(self):
        self._analyze_text(self.splash_text)

    def _analyze_link(self, link:str):
        ret = []
        request_process = threading.Thread(target=self._make_request_thread, args=(link, ret))

        request_process.start()
        request_process.join(1)

        if request_process.is_alive():
            print('Skipping iteration', self._iteration)
            return

        page = ret[0]
        text = self._get_text(page.content)
        self._analyze_text(text)

    def _analyze_text(self, text:str):
        for choice in self.search_phrases.keys():
            self.choice_counts[self.search_phrases[choice]] += self._assign_count(text, choice)
        self._evaluate()

###################################################################################
#Evaluation of search results

    def _evaluate(self):
        self._update_confidence()
        if (self._iteration == 1):
            print('shallow iteration')
        else:
            print('iteration', self._iteration, 'of', len(self.links) + 1)
        print('current confidence:', self.pretty_confidence, 'for guess of', self.guess)
        print('current duration:', time.time() - self.start_time)
        print('============================= best guess (' + self.pretty_confidence + ' confident):',
            self.true_guess)

    def _update_confidence(self):
        self._save_current_stats()

        total_count = sum(self.choice_counts.values())
        if total_count != 0:
            sorted_counts = sorted(self.choice_counts.keys(), 
                            key=lambda choice: self.choice_counts[choice], reverse=True)

            current_confidence = float(self.choice_counts[sorted_counts[0]]) / total_count
            for i in range(1, len(sorted_counts)):
                current_confidence -= float(self.choice_counts[sorted_counts[i]]) / total_count 

            self.confidence = current_confidence
            self.guess = sorted_counts[0] 

##################################################################################
#Natural language processing

    def _assign_count(self, text: str, phrase: str) -> int:  
        sentences = nltk.sent_tokenize(text)
        phrase_count = 0
       
        for sentence in sentences:
            occurences = sentence.count(phrase)
            if occurences > 0 and self.root_verb in sentence:
                phrase_count += self.RVF * occurences
                print(sentence)
            else:
                phrase_count += occurences
        
        if self.is_negated: phrase_count *= -1
        return phrase_count


    def _get_root_verb(self, sentence: str) -> str:

        root_verb, root_node_pos, dependency_tree = self._get_root_helper(sentence)

        verb_negated = False
        for node in dependency_tree:
            if node[0] == 'neg' and node[1] == root_node_pos:
                verb_negated = True
                break
        #Return the infinitive####################################
        return (root_verb, verb_negated) 

    def _to_search(self) -> list: # returns search words associated with their phrase
        valids = []
        for phrase in self.choices:
            valids.append((phrase, phrase))
            if len(phrase.split()) > 1:
                #tokenized_phrase = nltk.pos_tag(nltk.word_tokenize(phrase))
                #valids.extend([(token, phrase) for token, tag in tokenized_phrase
                #                if tag[:2] == 'NN' and token != phrase])
                root, _, _ = self._get_root_helper(phrase)
                if root != phrase:
                    valids.append((root, phrase))
        return dict(valids)
    
    def _modified_question(self) -> str:
        for choice in self.choices:
            question += ' ' + choice
        return question

    def _get_root_helper(self, sentence) -> str:
        dependency_tree = self.stanford_nlp.dependency_parse(sentence)
        i = 0
        while dependency_tree[i][0] != 'ROOT':
            i += 1
            if i == len(dependency_tree): 
                raise IndexError('No root node was found in dependency tree.')
        
        root_pos = dependency_tree[i][2] #this is 1-index based
        root = self.stanford_nlp.word_tokenize(sentence)[root_pos-1]
        return (root, root_pos, dependency_tree)

##################################################################################
#helper functions

    def _save_current_stats(self):
        if (self.confidence in self.guess_stats.keys()):
            self.guess_stats[self.confidence].append(self.guess)
        else:
            self.guess_stats[self.confidence] = [self.guess]

    def _get_links(self) -> tuple: # returns (list<links>, text)        
        page  = self._make_request(self._url, params=self._params())
        json_data = json.loads(page.content)

        links = [item['link'] for item in json_data['items']]
        text = u''.join([
            item['title'] + item ['htmlTitle'] + item['snippet'] + item['htmlSnippet']
            for item in json_data['items']
        ])       
        return (links, text.lower())

    def _make_request(self, url:str, params:dict = {}):
        return requests.get(url, params=params, headers=self._headers)

    def _make_request_thread(self, url:str, ret_list: list, params:dict = {}):
        try:
            ret_list.append(requests.get(url, params=params, headers=self._headers))
        except ConnectionError:
            print('Connection error for:', url)

    def _get_text(self, body):
        #This method and '_tag_visible' written by stack overflow user 'jbochi'
        soup = BeautifulSoup(body, 'html.parser')
        texts = soup.findAll(text=True)
        visible_texts = filter(self._tag_visible, texts)  
        return u" ".join(t.strip() for t in visible_texts)

    def _clean_choices(self, choices: list) -> list:
        for i in range(len(choices)):
            choices[i] = choices[i].lower()
        return choices

    def _params(self) -> dict:
        return {
            'q':self.question,
            'cx':self._cx,
            'key':self._api
        } 
    
    @staticmethod
    def _tag_visible(element):
        if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
            return False
        if isinstance(element, Comment):
            return False
        return True
    
    @staticmethod
    def create_nlp():
        #We dependency parse once because the first call always takes a while (reason unknown)
        from stanfordcorenlp import StanfordCoreNLP
        from secrets import SNLP_PATH
        nlp =  StanfordCoreNLP(SNLP_PATH)
        nlp.dependency_parse("This is a test sentence.")
        return nlp

##############################################################################
#additional properties

    @property
    def true_guess(self):
        #for now just returns guess with most hits
        return self.guess

    @property
    def pretty_confidence(self):
        return str(self.confidence * 100) + '%'

###############################################################################
#Runs a command line version of the answerer for testing purposes

def main():
    from ast import literal_eval as ast_eval
    nlp = Question.create_nlp()
    while True:
        try:
            question_text = ast_eval(input('Question: '))
            possible_answers = ast_eval(input('Choices: '))

            if question_text == 'q':
                break

            question = Question(question_text, possible_answers, nlp=nlp)
            print(question.answer(close=False))

        except RuntimeError as err:
            nlp.close()
            raise err
    nlp.close()

if __name__ == '__main__': main()
        