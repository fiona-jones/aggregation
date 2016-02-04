#!/usr/bin/env python
from aggregation_api import AggregationAPI
from classification import Classification
import rollbar
import requests
import os
import pickle
import helper_functions
import yaml
import json
from blob_clustering import BlobClustering
import parser
import json_transcription
import getopt
import sys
import folger
import annotate
import tarfile

__author__ = 'ggdhines'


class SubjectRetirement(Classification):
    def __init__(self,environment,param_dict):
        Classification.__init__(self,environment)
        assert isinstance(param_dict,dict)

        # to retire subjects, we need a connection to the host api, which hopefully is provided
        self.host_api = None
        self.project_id = None
        self.token = None
        self.workflow_id = None
        for key,value in param_dict.items():
            if key == "host":
                self.host_api = value
            elif key == "project_id":
                self.project_id = value
            elif key == "token":
                self.token = value
            elif key == "workflow_id":
                self.workflow_id = value

        self.num_retired = None
        self.non_blanks_retired = None

        self.to_retire = None

        assert (self.host_api is not None) and (self.project_id is not None) and (self.token is not None) and (self.workflow_id is not None)

    def __aggregate__(self,raw_classifications,workflow,aggregations):
        # start by looking for empty subjects

        self.to_retire = set()
        for subject_id in raw_classifications["T0"]:
            user_ids,is_subject_empty = zip(*raw_classifications["T0"][subject_id])
            if is_subject_empty != []:
                empty_count = sum([1 for i in is_subject_empty if i == True])
                if empty_count >= 3:
                    self.to_retire.add(subject_id)

        blank_retirement = len(self.to_retire)

        non_blanks = []

        # now look to see if everything has been transcribed
        for subject_id in raw_classifications["T3"]:
            user_ids,completely_transcribed = zip(*raw_classifications["T3"][subject_id])

            completely_count = sum([1 for i in completely_transcribed if i == True])
            if completely_count >= 3:
                self.to_retire.add(subject_id)
                non_blanks.append(subject_id)

            # # have at least 4/5 of the last 5 people said the subject has been completely transcribed?
            # recent_completely_transcribed = completely_transcribed[-5:]
            # if recent_completely_transcribed != []:
            #     complete_count = sum([1 for i in recent_completely_transcribed if i == True])/float(len(recent_completely_transcribed))
            #
            #     if (len(recent_completely_transcribed) == 5) and (complete_count >= 0.8):
            #         to_retire.add(subject_id)

        # don't retire if we are in the development environment
        if (self.to_retire != set()) and (self.environment != "development"):
            try:
                headers = {"Accept":"application/vnd.api+json; version=1","Content-Type": "application/json", "Authorization":"Bearer "+self.token}
                params = {"retired_subjects":list(self.to_retire)}
                # r = requests.post("https://panoptes.zooniverse.org/api/workflows/"+str(self.workflow_id)+"/links/retired_subjects",headers=headers,json=params)
                r = requests.post("https://panoptes.zooniverse.org/api/workflows/"+str(self.workflow_id)+"/links/retired_subjects",headers=headers,data=json.dumps(params))
                # rollbar.report_message("results from trying to retire subjects","info",extra_data=r.text)

            except TypeError as e:
                print e
                rollbar.report_exc_info()
        if self.environment == "development":
            print "we would have retired " + str(len(self.to_retire))
            print "with non-blanks " + str(len(self.to_retire)-blank_retirement)
            if not os.path.isfile("/home/ggdhines/"+str(self.project_id)+".retired"):
                pickle.dump(non_blanks,open("/home/ggdhines/"+str(self.project_id)+".retired","wb"))
            print str(len(self.to_retire)-blank_retirement)

        self.num_retired = len(self.to_retire)
        self.non_blanks_retired = len(self.to_retire)-blank_retirement

        return aggregations


class TranscriptionAPI(AggregationAPI):
    def __init__(self,project_id,environment,end_date=None):
        AggregationAPI.__init__(self,project_id,environment,end_date=end_date)

        # just to stop me from using transcription on other projects
        assert int(project_id) in [245,376]

    def __cluster__(self,used_shapes,raw_markings,image_dimensions):
        """
        run the clustering algorithm for a given workflow
        need to have already checked that the workflow requires clustering
        :param workflow_id:
        :return:
        """

        if raw_markings == {}:
            print "warning - empty set of images"
            # print subject_set
            return {}

        # start by clustering text
        print "clustering text"
        cluster_aggregation = self.text_algorithm.__aggregate__(raw_markings,image_dimensions)
        print "clustering images"
        image_aggregation = self.image_algorithm.__aggregate__(raw_markings,image_dimensions)

        cluster_aggregation = self.__merge_aggregations__(cluster_aggregation,image_aggregation)

        return cluster_aggregation

    def __setup__(self):
        AggregationAPI.__setup__(self)

        workflow_id = self.workflows.keys()[0]

        # set the classification algorithm which will retire the subjects
        classification_params = {"host":self.host_api,"project_id":self.project_id,"token":self.token,"workflow_id":workflow_id}
        self.__set_classification_alg__(SubjectRetirement,classification_params)

        self.instructions[workflow_id] = {}

        # set the function which will extract the relevant params for processing transcription annotations
        self.marking_params_per_shape["text"] = helper_functions.relevant_text_params

        # set up the text clustering algorithm
        # todo - this might not be necesary anymore
        additional_text_args = {"reduction":helper_functions.text_line_reduction}

        # load in the tag file if there is one
        api_details = yaml.load(open("/app/config/aggregation.yml","rb"))
        if "tags" in api_details[self.project_id]:
            additional_text_args["tags"] = api_details[self.project_id]["tags"]

        # now that we have the additional text arguments, convert text_algorithm from a class
        # to an actual instance
        if self.project_id == 245:
            self.text_algorithm = annotate.AnnotateClustering("text",self,additional_text_args)
        elif self.project_id == 376:
            self.text_algorithm = folger.FolgerClustering("text",self,additional_text_args)
        else:
            assert False

        self.image_algorithm = BlobClustering("image",None,{})

        self.only_retired_subjects = False
        self.only_recent_subjects = True

    def __cluster_output_with_colour__(self,workflow_id,ax,subject_id):
        """
        use colour to show where characters match and don't match between different transcriptions of
        the same text
        :param subject_id:
        :return:
        """
        selection_stmt = "SELECT aggregation FROM aggregations WHERE workflow_id = " + str(workflow_id) + " AND subject_id = " + str(subject_id)
        cursor = self.postgres_session.cursor()
        cursor.execute(selection_stmt)

        aggregated_text = cursor.fetchone()[0]["T2"]["text clusters"].values()
        assert isinstance(aggregated_text,list)
        # remove the list of all users
        aggregated_text = [a for a in aggregated_text if isinstance(a,dict)]

        # sort the text by y coordinates (should give the order in which the text is supposed to appear)
        aggregated_text.sort(key = lambda x:x["center"][2])

        for text in aggregated_text:
            ax.plot([text["center"][0],text["center"][1]],[text["center"][2],text["center"][3]],color="red")
            actual_text = text["center"][-1]
            atomic_text = self.cluster_algs["text"].__set_special_characters__(actual_text)[1]

            for c in atomic_text:
                if ord(c) == 27:
                    # no agreement was reached
                    print chr(8) + unicode(u"\u2224"),
                elif ord(c) == 28:
                    # the agreement was that nothing was here
                    # technically not a space but close enough
                    print chr(8) + " ",
                else:
                    print chr(8) + c,
            print

    def __readin_tasks__(self,workflow_id):
        if self.project_id == 245:
            # marking_tasks = {"T2":["image"]}
            marking_tasks = {"T2":["text","image"]}
            # todo - where is T1?
            classification_tasks = {"T0":True,"T3" : True}

            return classification_tasks,marking_tasks,{}
        elif self.project_id == 376:
            marking_tasks = {"T2":["text"]}
            classification_tasks = {"T0":True,"T3":True}

            print AggregationAPI.__readin_tasks__(self,workflow_id)

            return classification_tasks,marking_tasks,{}
        else:
            assert False

    def __summarize__(self,tar_path=None):
        num_retired = self.classification_alg.num_retired
        non_blanks_retired = self.classification_alg.non_blanks_retired

        stats = self.text_algorithm.stats

        old_time_string = self.previous_runtime.strftime("%B %d %Y")
        new_time_string = end_date.strftime("%B %d %Y")

        accuracy =  1. - stats["errors"]/float(stats["characters"])

        subject = "Aggregation summary for " + str(old_time_string) + " to " + str(new_time_string)

        body = "This week we have retired " + str(num_retired) + " subjects, of which " + str(non_blanks_retired) + " where not blank."
        body += " A total of " + str(stats["retired lines"]) + " lines were retired. "
        body += " The accuracy of these lines was " + "{:2.1f}".format(accuracy*100) + "% - defined as the percentage of characters where at least 3/4's of the users were in agreement."

        print self.__panoptes_call__("projects/"+str(self.project_id)+"/aggregations_export?admin=true")
        assert False
        if tar_path is not None:
            bucket = "s3://zooniverse-static/panoptes-uploads.zooniverse.org/"+str(self.project_id)+"/"
            s3 = boto3.resource('s3')
            try:
                s3.meta.client.head_bucket(Bucket=bucket)
            except botocore.exceptions.ClientError as e:
                # If a client error is thrown, then check that it was a 404 error.
                # If it was a 404 error, then the bucket does not exist.
                error_code = int(e.response['Error']['Code'])
                if error_code == 404:
                    s3.create_bucket(Bucket=bucket,CreateBucketConfiguration={'LocationConstraint': 'us-west-1'})

            object = s3.Object('mybucket', 'hello.txt')
            object.put(Body=open('/tmp/hello.txt', 'rb'))

            url = get_signed_url(604800, bucket, object)





        body += "\n Greg Hines \n Zooniverse \n \n PS This email was automatically generated."

        client = boto3.client('ses')
        response = client.send_email(
            Source='greg@zooniverse.org',
            Destination={
                'ToAddresses': [
                    'greg@zooniverse.org','victoria@zooniverse.org','matt@zooniverse.org'
                ]#,
                # 'CcAddresses': [
                #     'string',
                # ],
                # 'BccAddresses': [
                #     'string',
                # ]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'ascii'
                },
                'Body': {
                    'Text': {
                        'Data': body,
                        'Charset': 'ascii'
                    }
                }
            },
            ReplyToAddresses=[
                'greg@zooniverse.org',
            ],
            ReturnPath='greg@zooniverse.org'
        )

        print response

if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:],"shi:e:d:",["summary","project_id=","environment=","end_date="])
    except getopt.GetoptError:
        print 'transcription.py -i <project_id> -e: <environment> -d: <end_date>'
        sys.exit(2)

    environment = "development"
    project_id = None
    end_date = None
    summary = False

    for opt, arg in opts:
        if opt in ["-i","--project_id"]:
            project_id = int(arg)
        elif opt in ["-e","--environment"]:
            environment = arg
        elif opt in ["-d","--end_date"]:
            end_date = parser.parse(arg)
        elif opt in ["-s","--summary"]:
            summary = True

    assert project_id is not None

    with TranscriptionAPI(project_id,environment,end_date) as project:
        project.__setup__()
        if environment == "production":
            project.__migrate__()
        # project.__migrate__()
        print "done migrating"
        # project.__aggregate__(subject_set = [671541,663067,664482,662859])
        project.__aggregate__()

        if summary:
            project.__add_metadata__()

            tar_path = "/tmp/"+str(project_id)+".tar.gz"
            t = tarfile.open(tar_path,mode="w:gz")
            json.dump(project.overall_aggregation,open("/tmp/"+str(project_id)+".txt","wb"))
            t.add("/tmp/"+str(project_id)+".txt")
            t.close()

            project.__summarize__(tar_path)
            print "hello?"