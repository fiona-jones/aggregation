#!/usr/bin/env python
__author__ = 'greghines'
import numpy as np
import os
import pymongo
import sys
import urllib
import matplotlib.cbook as cbook
from PIL import Image
import matplotlib.pyplot as plt
import warnings
import random

if os.path.exists("/home/ggdhines"):
    sys.path.append("/home/ggdhines/PycharmProjects/reduction/experimental/clusteringAlg")
else:
    sys.path.append("/home/greg/github/reduction/experimental/clusteringAlg")
#from divisiveDBSCAN import DivisiveDBSCAN
from divisiveDBSCAN_multi import DivisiveDBSCAN

if os.path.exists("/home/ggdhines"):
    base_directory = "/home/ggdhines"
else:
    base_directory = "/home/greg"

client = pymongo.MongoClient()
db = client['condor_2014-11-06']
classification_collection = db["condor_classifications"]
subject_collection = db["condor_subjects"]


to_sample_from = list(subject_collection.find({"classification_count":10}))

for subject_count,subject in enumerate(random.sample(to_sample_from,10)):
    if subject_count == 10:
        break
    zooniverse_id = subject["zooniverse_id"]
    url = subject["location"]["standard"]

    slash_index = url.rfind("/")
    object_id = url[slash_index+1:]


    annotation_list = []
    user_list = []

    for user_index,classification in enumerate(classification_collection.find({"subjects.zooniverse_id":zooniverse_id})):

        try:
            mark_index = [ann.keys() for ann in classification["annotations"]].index(["marks",])
            markings = classification["annotations"][mark_index].values()[0]

            for animal in markings.values():
                scale = 1.875
                x = scale*float(animal["x"])
                y = scale*float(animal["y"])
                animal_type = animal["animal"]
                if animal_type != "carcassOrScale":
                    annotation_list.append((x,y))
                    user_list.append(user_index)

        except ValueError:
            pass

    user_identified_condors,condor_clusters,noise__ = DivisiveDBSCAN(3).fit(annotation_list,user_list,debug=True)
    if not(os.path.isfile(base_directory+"/Databases/condors/images/"+object_id)):
        urllib.urlretrieve (url, base_directory+"/Databases/condors/images/"+object_id)

    image_file = cbook.get_sample_data(base_directory+"/Databases/condors/images/"+object_id)
    image = plt.imread(image_file)

    fig, ax = plt.subplots()
    im = ax.imshow(image)
    #plt.show()
    #
    if user_identified_condors != []:
        x,y = zip(*user_identified_condors)
        plt.plot(x,y,'.',color='blue')

    plt.show()

