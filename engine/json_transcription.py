#!/usr/bin/env python
__author__ = 'ggdhines'
from transcription import Tate
import json
from latex_transcription import get_updated_tags

project_id = 245
environment = "development"
workflow_id = 121
transcription_task = "T2"

project_id = 376
workflow_id = 205

first = True
count = 0

replacement_tags = get_updated_tags(project_id)

with open("/tmp/transcription.json","wb") as f:
    with Tate(project_id,environment) as project:
        f.write("[")
        for subject_id,aggregations in project.__yield_aggregations__(workflow_id):

            empty = True

            if "T2" not in aggregations:
                print "skipping"
                continue

            for cluster_index,cluster in aggregations["T2"]["text clusters"].items():
                print cluster
                if cluster_index == "all_users":
                    continue

                if cluster["num users"] < 2:
                    continue

                if empty and not first:
                    f.write(",")

                if first:
                    first = False



                if empty:
                    m = project.__get_subject_metadata__(subject_id)
                    metadata = m["subjects"][0]["metadata"]
                    metadata = json.dumps(metadata)
                    # metadata = metadata.encode('ascii','ignore')
                    f.write("{\"subject_id\": " + str(subject_id) + ", \"metadata\": " + metadata + ",")
                    f.write("\"individual_transcriptions\":[")
                    transcriptions = project.__sort_annotations__(workflow_id,[subject_id])[1]
                    first = True
                    for ii,(user_id,transcription,tool) in enumerate(transcriptions["T2"]["text"][subject_id]):
                        if transcription is None:
                            continue
                        coord = transcription[:-1]
                        individual_text = transcription[-1]
                        if "\n" in individual_text:
                            continue

                        individual_text = individual_text.replace("\\","\\\\")
                        individual_text = individual_text.replace("\"","\\\"")

                        if not first:
                            f.write(",")
                        first = False
                        f.write("{")
                        f.write("\"user_id\":"+str(user_id)+",")
                        f.write("\"coordinates\":"+str(list(coord))+",")
                        try:
                            individual_text = individual_text.encode('ascii','ignore')
                            f.write("\"text\": \""+str(individual_text) + "\"")
                        except UnicodeEncodeError:
                            print individual_text
                            raise
                        f.write("}")



                    f.write("],\"aggregated_text\":[")
                    f.write("{\"coordinates\":" + str(cluster["center"][:-1])+", \"text\":\"")
                else:
                    f.write(",{\"coordinates\":" + str(cluster["center"][:-1])+", \"text\":\"")
                empty = False

                line = ""



                agreement = True
                differences = {}

                # for folger this will allow us to remove sw- from all of the tags
                # for both folger and annotate, we will set <unclear>.*</unclear> to just <unclear></unclear>
                aggregated_line = cluster["center"][-1]
                assert isinstance(aggregated_line,str)
                for old,new in replacement_tags.items():
                    aggregated_line = aggregated_line.replace(old,new)

                for c_i,c in enumerate(aggregated_line):
                    if ord(c) in [24,27]:
                        agreement = False

                        char_options = [(ii,individual_text[c_i]) for ii,(coord,individual_text) in enumerate(cluster["cluster members"])]

                        for ii,c in char_options:
                            if ord(c) != 24:
                                if c == "\"":
                                    c = "\\\""
                                if c == "\\":
                                    c = "\\\\"

                                if ii not in differences:
                                    differences[ii] = c
                                else:
                                    differences[ii] += c
                            else:
                                if ii not in differences:
                                    differences[ii] = ""

                        # options = set([individual_text[c_i] for coord,individual_text in cluster["cluster members"]])

                    else:
                        if not agreement:
                            line += "<disagreement>"
                            for c in set(differences.values()):
                                line += "<option>"+c+"</option>"
                            line += "</disagreement>"
                            differences = {}


                        agreement = True
                        if c == "\"":
                            line += "\\\""
                        elif c == "\\":
                            line += "\\\\"
                        else:
                            line += c

                f.write(line + "\"")
                f.write(",\"individual_transcriptions\":[")
                for ii,(coords,individual_text) in enumerate(cluster["cluster members"]):
                    # again, convert the tags to the ones needed by Folger or Tate (as opposed to the ones
                    # zooniverse is using)
                    assert isinstance(individual_text,str)
                    for old,new in replacement_tags.items():
                        individual_text = individual_text.replace(old,new)

                    temp_text = individual_text
                    temp_text = temp_text.replace("\\","\\\\")
                    temp_text = temp_text.replace("\"","\\\"")


                    skip = 0
                    is_skip = False

                    # we need to "rebuild" the individual text so that we can insert <skip>X</skip>
                    # to denote that MAFFT inserted X spaces into the line
                    individual_text = ""
                    for c in temp_text:
                        if ord(c) in [24,27]:
                            is_skip = True
                            skip += 1
                        else:
                            if is_skip:
                                individual_text += "<skip>"+str(skip)+"</skip>"
                                skip = 0
                                is_skip = 0
                            individual_text += c


                    if ii > 0:
                        f.write(",")
                    f.write("{\"coordinates\":"+str(coords)+",\"text\":\""+individual_text+"\"}")

                f.write("]}")


            if not empty:
                f.write("]}")
                # break
                count += 1

        f.write("]")

with open("/tmp/transcription.json","r") as f:
    transcriptions = f.read()
    s = json.loads(transcriptions)