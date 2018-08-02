import trivia
import json
import string
from threading import Thread

def main(k=0, n=100):
    qdata = get_qdata()
    data_length = k+n#len(qdata)

    active_threads = []
    results = []

    while (k < data_length):
        #if len(active_threads) < 5:
        #    thread = Thread(target=(lambda question, answers, correct, results: 
        #                       results.append(int(is_correct(question, answers, correct)))),
        #                       args=(qdata[k][0], qdata[k][1], qdata[k][2], results))
        #    thread.start()
        #    k += 1
        #    print("Progress: " + str(float(len(results))/data_length*100) \                                                                    + "%")
        #active_threads = [t for t in active_threads if t.is_alive()]
        results.append(int(is_correct(qdata[k][0], qdata[k][1], qdata[k][2])))
        k+=1
        print("Progress: " + str(float(len(results))/data_length*100))

    for thread in active_threads:
        thread.join()

    print("Results: ")
    print("Successes: " + str(sum(results)) + "/" + str(n))
    print("Percent correct: " + str(float(sum(results))/n))
    

def get_qdata():
    with open('./DB.json') as json_data:
        question_list = json.loads(json_data.read())
        question_data = []
        for question_info in question_list:
            question = question_info['question']
            question = only_letters(question)
            answers = [answer['text'] for answer in question_info['answers']]
            correct_answer = [answer['text'] 
                             for answer in question_info['answers']
                             if answer['correct']]
            if len(correct_answer) == 0:
                continue
            correct_answer = correct_answer[0]
            correct_answer = only_letters(correct_answer)
            for i in range(len(answers)):
                answers[i] = only_letters(answers[i])
            question_data.append((question, answers, correct_answer))
    return question_data
            
def is_correct(question: str, answers: list, correct_answer: str) -> bool:
    q = trivia.Question(question, answers)
    guess = q.answer()
    print(guess == correct_answer)
    return guess == correct_answer

def only_letters(s:str) -> str:
    valids = []
    for character in s:
        if character in string.ascii_letters or character in ' 1234567890':
            valids.append(character.lower())
    return ''.join(valids)