import sys
import redis
from gdg.command import Command
from gdg.management_commands import ManagementCommands
from datetime import datetime
from uuid import uuid4
import threading


DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ00:00"

VERBOSE_DATETIME_FORMAT = "%d-%m-%Y:%H:%M"

cache = redis.Redis()


class Exam(threading.Thread):
    def __init__(self, r, channel, publisher):
        threading.Thread.__init__(self)
        self.redis = r
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channel)
        self.publisher = publisher
        self.channel = channel

    def run(self):
        for item in self.pubsub.listen():
            if item['type'] == 'message':
                item['data'] = item['data'].decode()
                if item['data'] == "start":
                    self.publisher.publish(self.channel, "ask")
                elif item['data'] == "ask":
                    word = self.publisher.srandmember(Word.CACHE_LIST_ALL_WORDS).decode()
                    self.publisher.publish(self.channel, "q:{}".format(word))
                elif item['data'].startswith("a:"):
                    raw_answer = item['data'][2:]
                    key, answer = raw_answer.split(":")

                    word = Word(key=key, from_redis=True)

                    pipe = self.publisher.pipeline()
                    score = word.number_of_correct_replies / (word.number_of_asked + 1)
                    if answer == word.value:
                        self.publisher.publish(self.channel, "r:Correct Answer!".format(word))
                        pipe.hincrby(word.redis_object_key, "number_of_correct_replies", 1)
                        score = (word.number_of_correct_replies + 1) / (word.number_of_asked + 1)
                    else:
                        self.publisher.publish(self.channel, "r:Wrong Answer!".format(word))
                    pipe.hincrby(word.redis_object_key, "number_of_asked", 1)
                    pipe.zadd(word.CACHE_LIST_BY_SCORE, word.key, score)
                    pipe.execute()
                    self.publisher.publish(self.channel, "ask")
                elif item['data'] == "KILL" or item['data'] == "INT":
                    self.pubsub.unsubscribe()
                    break


class Word(object):
    CACHE_OBJECT_PREFIX = "Words"
    CACHE_OBJECT_KEY_DELIMITER = ":"
    CACHE_LIST_BY_DATE = "List-By-Date"
    CACHE_LIST_BY_LEX = "List-By-Lex"
    CACHE_LIST_BY_SCORE = "List-By-Score"
    CACHE_LIST_ALL_WORDS = "All-Words"

    def __init__(self, from_redis=False, **kwargs):
        self.key = kwargs.get('key')
        if not self.key:
            raise KeyError()
        self.redis_object_key = "{prefix}{delimiter}{key}".format(
            prefix=self.CACHE_OBJECT_PREFIX,
            delimiter=self.CACHE_OBJECT_KEY_DELIMITER,
            key=self.key)

        self.data = self.decode_kwargs(
            cache.hgetall(self.redis_object_key)) if from_redis else kwargs

        self.value = self.data.get('value')

        self.creation_time = self.data.get('creation_time', datetime.now().strftime(DATETIME_FORMAT))
        self.last_update_time = self.data.get('last_update_time',
                                           datetime.now().strftime(DATETIME_FORMAT))
        self.number_of_asked = int(self.data.get('number_of_asked', 0))
        self.number_of_correct_replies = int(self.data.get('number_of_correct_replies', 0))

    @staticmethod
    def decode_kwargs(kw):
        data = {}
        for k, v in kw.items():
            data[k.decode()] = v.decode()
        return data

    def as_redis_object(self):
        return {
            "key": self.key,
            "value": self.value,
            "creation_time": self.creation_time,
            "last_update_time": self.last_update_time,
            "number_of_asked": self.number_of_asked,
            "number_of_correct_replies": self.number_of_correct_replies,
        }

    def update_time(self):
        self.last_update_time = datetime.now().strftime(DATETIME_FORMAT)


class Add(Command):
    CMD_NAME = 'add'
    HELP = 'Adds new words'
    PARAMS = [
        {'name': 'w', 'required': True, 'help': 'Word to add'},
        {'name': 't', 'required': True, 'help': 'Translation of given word'},
    ]

    def run(self):
        # todo check if possible keys having multiple values
        # todo check if multi add needed

        if not self.manager.args.t:
            print("Translation cannot be empty.")
            return

        try:
            word = Word(key=self.manager.args.w, value=self.manager.args.t)
        except KeyError:
            print("Word cannot be empty.")
            return

        if cache.exists(word.redis_object_key):
            print("Word: {} already in there!".format(word.key))
            return

        pipe = cache.pipeline()
        pipe.hmset(word.redis_object_key, word.as_redis_object())
        pipe.zadd(word.CACHE_LIST_BY_DATE, word.key,
                  datetime.strptime(word.creation_time, DATETIME_FORMAT).timestamp())
        pipe.zadd(word.CACHE_LIST_BY_LEX, word.key, 0)
        pipe.zadd(word.CACHE_LIST_BY_SCORE, word.key, 0)
        pipe.sadd(word.CACHE_LIST_ALL_WORDS, word.key)
        pipe.execute()

        print("{key} -> {value}".format(key=word.key, value=word.value))


class Update(Command):
    CMD_NAME = 'update'
    HELP = 'Updates an already existing word, if the given key does not exist, returns.'
    PARAMS = [
        {'name': 'ow', 'required': True, 'help': 'Word which will be updated'},
        {'name': 'nw', 'help': 'New value of word if it is intended to be changed'},
        {'name': 't', 'help': 'New translation of the word if it is passed as argument'},
    ]

    def run(self):
        if not (self.manager.args.nw or self.manager.args.t):
            print("Invalid arguments. --nw or --t must be passed!")
            return

        if self.manager.args.nw and self.manager.args.t:
            print("Invalid arguments. --nw and --t cannot be passed at the same time!")
            return

        try:
            word = Word(key=self.manager.args.ow, from_redis=True)
            if self.manager.args.nw:
                key = self.manager.args.nw
                new_word = Word(key=key)
                cache.exists(new_word.redis_object_key)

                # renames old key only if new key does not already exists
                if cache.renamenx(word.redis_object_key, new_word.redis_object_key):
                    pipe = cache.pipeline()
                    pipe.hmset(
                        new_word.redis_object_key,
                        {
                            'key': new_word.key,
                            'last_update_time': datetime.now().strftime(DATETIME_FORMAT)
                        }
                    )

                    # remove old word from lists
                    pipe.zrem(word.CACHE_LIST_BY_DATE, word.key)
                    pipe.zrem(word.CACHE_LIST_BY_LEX, word.key)
                    pipe.zrem(word.CACHE_LIST_BY_SCORE, word.key)
                    pipe.srem(word.CACHE_LIST_ALL_WORDS, word.key)

                    # add new word to lists

                    # initial creation time lies in the firs object
                    pipe.zadd(new_word.CACHE_LIST_BY_DATE, new_word.key,
                              datetime.strptime(word.creation_time, DATETIME_FORMAT).timestamp())
                    pipe.zadd(new_word.CACHE_LIST_BY_LEX, new_word.key, 0)
                    pipe.zadd(new_word.CACHE_LIST_BY_SCORE, new_word.key, 0)
                    pipe.sadd(new_word.CACHE_LIST_ALL_WORDS, new_word.key)
                    pipe.execute()
                else:
                    print("New key is already in there!")
                    return
                print("Word: {} changed to {}.".format(word.key, new_word.key))
            if self.manager.args.t:
                value = self.manager.args.t
                if value != word.value:
                    word.update_time()
                    cache.hmset(word.redis_object_key,
                                {'value': value, 'last_update_time': word.last_update_time})
                    print(
                        "Value of word: {} changed from {} to {}.".format(word.key, word.value,
                                                                          value))
                else:
                    print("Value of word: {} is already {}.".format(word.key, value))
        except KeyError:
            print("There is no such word: {}".format(self.manager.args.ow))
            return


class Delete(Command):
    CMD_NAME = 'delete'
    HELP = 'Deletes a word'
    PARAMS = [
        {'name': 'w', 'required': True, 'help': 'Word to delete'},
    ]

    def run(self):
        word = Word(key=self.manager.args.w)
        pipe = cache.pipeline()
        pipe.delete(word.redis_object_key)
        pipe.zrem(word.CACHE_LIST_BY_DATE, word.key)
        pipe.zrem(word.CACHE_LIST_BY_LEX, word.key)
        pipe.zrem(word.CACHE_LIST_BY_SCORE, word.key)
        pipe.srem(word.CACHE_LIST_ALL_WORDS, word.key)
        result = pipe.execute()
        if not any(result):
            print("There is no such word: {}".format(word.key))

        if all(result):
            print('Word:{} gracefully deleted!'.format(word.key))


class Read(Command):
    CMD_NAME = 'read'
    HELP = 'Read a word'
    PARAMS = [
        {'name': 'w', 'required': True, 'help': 'Word to read'},
        {'name': 'd', 'help': 'Details'},
    ]

    def run(self):
        try:
            word = Word(key=self.manager.args.w, from_redis=True)
            if not word.value:
                print("There is no such word: {}".format(self.manager.args.w))
                return
            print("{} ==> {}".format(word.key, word.value))
            if self.manager.args.d:
                print("Correct replies: {cr}/{ask}".format(cr=word.number_of_correct_replies,
                    ask=word.number_of_asked))
                lu_time = datetime.strptime(word.last_update_time, DATETIME_FORMAT)
                c_time = datetime.strptime(word.creation_time, DATETIME_FORMAT)
                print("Last Updated At: {}".format(lu_time.strftime(VERBOSE_DATETIME_FORMAT)))
                print("Created At: {}".format(c_time.strftime(VERBOSE_DATETIME_FORMAT)))
        except KeyError:
            print("There is no such word: {}".format(self.manager.args.w))
            return


class List(Command):
    CMD_NAME = 'list'
    HELP = 'Lists words according to the arguments'
    PARAMS = [
        {'name': 'd', 'help': 'Lists the words by creation date if it will be set'},
        {'name': 'l', 'help': 'Lists the words by alphabetical order if it will be set'},
        {'name': 's', 'help': 'Lists the words by scores if it will be set'},

        {'name': 'o', 'help': 'Order of the list, asc or desc'},

        {'name': 'ps', 'type': int, 'help': 'Number words in a single page'},
        {'name': 'p', 'type': int, 'help': 'Number of page which will be retrieved'},
        {'name': 'c', 'type': int, 'help': 'Cursor if previous query returns with it'},


    ]

    def run(self):
        counter = 0
        for item in [self.manager.args.d, self.manager.args.l, self.manager.args.s]:
            if item:
                counter += 1
        if counter > 1:
            print("Invalid arguments, need one at a time from d, l, or s!")
            return

        if self.manager.args.p and self.manager.args.c:
            print("Invalid args p and c. One at a time.")
            return

        query = {}

        if self.manager.args.d:
            query['from'] = Word.CACHE_LIST_BY_DATE
        elif self.manager.args.l:
            query['from'] = Word.CACHE_LIST_BY_LEX
        elif self.manager.args.s:
            query['from'] = Word.CACHE_LIST_BY_SCORE
        else:
            if self.manager.args.o:
                print("Order cannot be evaluated if d, l, or s not set.")
                return
            query['from'] = Word.CACHE_LIST_ALL_WORDS

        query['order'] = self.manager.args.o or "asc"

        query['page_size'] = self.manager.args.ps or 10
        query['page'] = self.manager.args.p or 1
        query['cursor'] = self.manager.args.c or 0

        cursor = None
        if query['from'] == Word.CACHE_LIST_ALL_WORDS:
            total_number = cache.scard(query['from'])
            cursor, result = cache.sscan(query['from'], cursor=query['cursor'],
                                         count=query['page_size'])
            result = [item.decode() for item in result]
        else:
            total_number = cache.zcard(query['from'])
            desc = query['order'] == 'desc'
            start = (query['page'] - 1) * query['page_size']
            end = start + query['page_size'] - 1
            result = [item.decode() for item in cache.zrange(query['from'], start, end, desc=desc)]

        print("Listing {} in {}".format(len(result), total_number))
        if cursor is not None:
            print("Cursor: {}".format(cursor))
        for i, word in enumerate(result):
            print("{index}) {word}".format(word=word, index=i+1))


class Quiz(Command):
    CMD_NAME = 'quiz'
    HELP = 'Starts a quiz'
    PARAMS = [
        {'name': 'q', 'type': int, 'required': True, 'help': 'Number of questions'},
    ]

    def run(self):
        if self.manager.args.q and cache.exists(Word.CACHE_LIST_ALL_WORDS):
            num_of_q = self.manager.args.q
            channel_name = uuid4().hex

            quiz = Exam(redis.Redis(), channel_name, redis.Redis())
            quiz.start()

            print("Quiz started with {} questions".format(num_of_q))

            user_pubsub = redis.Redis().pubsub()
            user_pubsub.subscribe([channel_name])

            cache.publish(channel_name, "start")
            counter = 0

            for item in user_pubsub.listen():
                if item['type'] == 'message':
                    item['data'] = item['data'].decode()
                    if item['data'].startswith("q:") and counter != num_of_q:
                        print("Q{}) {}".format(counter+1, item['data'][2:]))
                        user_answer = input()
                        counter += 1
                        if user_answer == "q!":
                            cache.publish(channel_name, "INT")
                        cache.publish(
                            channel_name,
                            "a:{word}:{answer}".format(word=item['data'][2:], answer=user_answer)
                        )

                    if item['data'].startswith("r:"):
                        print(item['data'][2:])
                        if counter == num_of_q:
                            cache.publish(channel_name, "KILL")
                    if item['data'] == "KILL":
                        print("End of quiz.")
                        user_pubsub.unsubscribe()
                        return

                    if item['data'] == "INT":
                        print("Interrupted!")
                        user_pubsub.unsubscribe()
                        return
        else:
            print("There is no word to ask!")


if __name__ == '__main__':
    ManagementCommands(sys.argv[1:])
