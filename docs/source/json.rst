Understanding Aggregation Results in JSON Format
================================================

If you have the aggregation results from Annotate or Shakespeare's World, they are in JSON format. The advantage of JSON over CSV is flexibility. This wiki is a brief discussion of how to deal with them. The following code is in Python - JSON and Python are a natural fit and Greg (the person who wrote the Annotate/Shakespeare's World aggregation code) works in Python. That said, other languages should support JSON - it may just not be as simple.

To load a JSON file in Python, use the following code ::

    import json
    with open('aggregation_results.json') as data_file:
        aggregation_results = json.load(data_file)

In Python JSON variables are simply either a dictionary, list or literal values such as strings or numbers. JSON variables are recursively defined so each element of a dictionary/list is itself a JSON variable. Literal values are the base cases.

To print out the data in json we can use pretty print (we could also just do "print data" or "print(data)" in Python 3 but this would give an un-readable wall of text) ::

    print(json.dumps(aggregation_results, sort_keys=True, indent=4, separators=(',', ': ')))

Note while the aggregation engine is written in Python 2, for compatibility, all of the print statements have been done in Python 3. To allow for Python 3 style print statements (with the brackets) in Python 2, simply put at the top of your code the line ::

    from __future__ import print_function

Aggregation_results is massive and even with nice formatting, the output is going to be overwhelming. So let's break it down. The top level of the json results is a dictionary where each key is a subject id value which maps to the aggregation results for that subject. (The subject ids are just numerical values created by Zooniverse, for example "1281157". This numbers won't mean anything to you - they are just Zooniverse's way of uniquely identifying subjects (i.e. documents). This is probably not the best way to identify each subject but we never settled on a better way - so if you have a specific document you are searching for you will need to search through the whole list.)
The aggregation results will only contain subjects which have been retired. To see all of the subject ids with aggregation results simply do ::

    print(aggregation_results.keys())

An example result might be ::

    [u'1274968', u'1274969', u'1276058', u'1279124', u'1273572', u'1274458', u'1273570', u'1274964', u'1273574', u'1273575' ...]

Note that the subject ids are actually strings (not totally sure why that is the case but doesn't seem to cause any trouble). The u'' simply means unicode (for the purposes of printing out subject ids, just think of strings)

To print out the aggregation results for one subject we can do ::

    print(json.dumps(aggregation_results["1274968"], sort_keys=True, indent=4, separators=(',', ': ')))

There is still a lot of output. aggregation_results["1274968"] is a dictionary so again we can look at the keys in the dictionary ::

    print(aggregation_results["1274968"].keys())


This will give ::

    ['text', 'raw transcriptions', 'metadata']

1. 'text' - the aggregated text
2. 'raw transcriptions' - the original transcriptions for the given subject. Useful if you want to know which transcriptions were ignored
3. 'metadata' - the metadata provided by Tate/Folger. Useful for figuring out which document each subject is

Looking at the text aggregation results - the aggregation results are stored in a list. Each element in the list refers to cluster of transcriptions, all transcribing the same text (each transcription in the cluster is by a different user).
Each cluster has a number of properties ::

    ['aggregated_text', 'individual transcriptions', 'coordinates', 'accuracy']

1. 'aggregated_text' - the aggregate text (probably what you are most interested in)
2. 'individual transcriptions' - the individual transcriptions in the cluster
3. 'accuracy' - how much agreement there is between all of the transcriptions in the given cluster

So to iterate over all of the aggregate transcriptions, we could do ::

    for cluster in aggregation_results["1274968"]["text"]:
        print(line)

All of the tags should be in the format that Folger asked for (e.g. "<del>"). In the aggregate text, there is a special character with ASCII value 27. This is a non-printing character which corresponds to when users were not in agreement about a specific character. Agreement is defined as when at least 2/3's of the users have given the same character.

Accuracy is a measure of how the users are in agreement (i.e. for what percentage of characters was there at least 2/3's agreement). If there is disagreement for a character you can refer back to the individual transcriptions to try and figure out what the best choice is.

To get a list of all the points of disagreement for a given line, we could use ::

    [i for i,c in enumerate(line) if ord(c) == 27]

All of the individual lines of text have been formatted to be the same length. So if for line 2 (i.e. the third text in the list of aggregated text, Python is zero indexed) there is a disagreement at index 3, we can get all of the possibilities with ::

    individual_transcriptions = aggregation_results["1274968"]["individual transcriptions"][2]
    different_possibilities = set([t[3] for t in individual_transcriptions])

Here "set()" just makes sure to give us the unique possibilities. There is one special character with ASCII value 24 which means that the aggregation engine has determined that the user "skipped" a character (e.g. transcribed "ello" when every one else transcribed "hello"). Note that differences in capitalization are settled favouring the capitalized letter and double (or triple spaces) are ignored.

\x1b