# Dive Into Redis Sample Project - GDG 2017

Sample application with Redis.

Basically, it is a vocabulary application that it can store the words 
as key value pairs within their translations. It also provides a pop-quiz
mechanism to test user him/herself. 

## Requirements 

* [Redis](redis.io)
* [Python 3](https://www.python.org/download/releases/3.0/)
* [redis-py](https://github.com/andymccurdy/redis-py)

## Run

* Start redis server
* Run the commands

## Commands
```
$ python vocabulary.py --help
usage: vocabulary.py [-h] {add,update,delete,read,list,quiz} ...

optional arguments:
  -h, --help            show this help message and exit

Possible commands:
  {add,update,delete,read,list,quiz}
    add                 Adds new words
    update              Updates an already existing word, if the given key
                        does not exist, returns.
    delete              Deletes a word
    read                Read a word
    list                Lists words according to the arguments
    quiz                Starts a quiz
```

### Add
```
$ python vocabulary.py add --help
usage: vocabulary.py add [-h] -w [W] -t [T]

optional arguments:
  -h, --help  show this help message and exit
  -w [W]      Word to add
  -t [T]      Translation of given word
```
#### Examples:

```
$ python vocabulary.py add -w example -t örnek
>> example -> örnek
```

### Update

```
$ python vocabulary.py update --help
usage: vocabulary.py update [-h] -ow [OW] [-nw [NW]] [-t [T]]

optional arguments:
  -h, --help  show this help message and exit
  -ow [OW]    Word which will be updated
  -nw [NW]    New value of word if it is intended to be changed
  -t [T]      New translation of the word if it is passed as argument
```
#### Examples:
```
$ python vocabulary.py update -ow examlpe -nw example
>> Word: examlpe changed to example.
$ python vocabulary.py update -ow example -t örnek
>> Value of word: example changed from örenk to örnek.
```
### Read
```
$ python vocabulary.py read --help
usage: vocabulary.py read [-h] -w [W] [-d [D]]

optional arguments:
  -h, --help  show this help message and exit
  -w [W]      Word to read
  -d [D]      Details
```
#### Examples:
```
$ python vocabulary.py read -w example
>> example ==> örnek
$ python vocabulary.py read -w example -d true
example ==> örnek
Correct replies: 0/0
Last Updated At: 02-12-2017:20:35
Created At: 02-12-2017:20:32
```

### List
```
$ python vocabulary.py list --help
usage: vocabulary.py list [-h] [-d [D]] [-l [L]] [-s [S]] [-o [O]] [-ps [PS]]
                          [-p [P]] [-c [C]]

optional arguments:
  -h, --help  show this help message and exit
  -d [D]      Lists the words by creation date if it will be set
  -l [L]      Lists the words by alphabetical order if it will be set
  -s [S]      Lists the words by scores if it will be set
  -o [O]      Order of the list, asc or desc
  -ps [PS]    Number words in a single page
  -p [P]      Number of page which will be retrieved
  -c [C]      Cursor if previous query returns with its
```
#### Examples:

List without any order:
```
$ python vocabulary.py list
Listing 5 in 5
Cursor: 0
1) evolution
2) revolution
3) resistence
4) freedom
5) example

$ python vocabulary.py list -ps 3
Listing 3 in 5
Cursor: 3
1) evolution
2) revolution
3) resistence

$ python vocabulary.py list -ps 3 -c 3
Listing 2 in 5
Cursor: 0
1) freedom
2) example

```
List by creation date:

```
$ python vocabulary.py list -d true
Listing 5 in 5
1) freedom
2) evolution
3) revolution
4) resistence
5) example

$ python vocabulary.py list -d true -o desc
Listing 5 in 5
1) example
2) resistence
3) revolution
4) evolution
5) freedom

$ python vocabulary.py list -d true -o desc -ps 3
Listing 3 in 5
1) example
2) resistence
3) revolution

$ python vocabulary.py list -d true -o desc -ps 3 -p 2
Listing 2 in 5
1) evolution
2) freedom

```

> For by score(-s) and alphabetically(-l) listing all options 
> are the same with the creation date.  

### Delete
```
$ python vocabulary.py delete --help
usage: vocabulary.py delete [-h] -w [W]

optional arguments:
  -h, --help  show this help message and exit
  -w [W]      Word to delete
```

#### Examples:

```
$ python vocabulary.py delete -w example
>> Word:example gracefully deleted!
```


### Quiz
```
$ python vocabulary.py quiz --help
usage: vocabulary.py quiz [-h] -q [Q]

optional arguments:
  -h, --help  show this help message and exit
  -q [Q]      Number of questions
```
#### Examples:
```
$ python vocabulary.py quiz -q 3
>> Quiz started with 3 questions
>> Q1) revolution
devrim
>> Correct Answer!
>> Q2) evolution
devrim
>> Wrong Answer!
>> Q3) evolution
evrim
>> Correct Answer!
>> End of quiz.
```

> Writing 'q!' as an answer will halt the quiz.