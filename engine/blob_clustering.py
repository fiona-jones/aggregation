from __future__ import print_function

import clustering
import matplotlib.pyplot as plt
import itertools
import math
import numpy as np
import cv2
import matplotlib.pyplot as plt
from scipy import stats


class EmptyPolygon(Exception):
    pass


class BlobClustering(clustering.Cluster):
    def __init__(self,shape,project,additional_params):
        assert shape != "point"
        clustering.Cluster.__init__(self,shape,project,additional_params)
        self.rectangle = (shape == "rectangle") or (shape == "image")

    def __find_outlined_areas__(self,user_ids,markings,dimensions):
        """
        give a set of polygon markings made by people, determine the area(s) in the image which were outlined
        by enough people
        """
        unique_users = set(user_ids)

        aggregate_polygon_list = []

        for i in unique_users:
            polygons_by_user = [j for j,u in enumerate(user_ids) if u == i]
            # tools_per_user = [tools[j] for j in polygons_by_user]
            polygons_as_arrays = [np.asarray(markings[j],np.int) for j in polygons_by_user]
            # print(tools_per_user)


            template = np.zeros(dimensions,np.uint8)

            # start by drawing the outline of the area
            cv2.polylines(template,polygons_as_arrays,True,255)

            # now take the EXTERNAL contour
            im2, contours, hierarchy = cv2.findContours(template,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            template2 = np.zeros(dimensions,np.uint8)
            cv2.drawContours(template2,contours,-1,1,-1)

            aggregate_polygon_list.append(template2)

        aggregate_polygon = np.sum(aggregate_polygon_list,axis=0,dtype=np.uint8)

        # the threshold determines the minimum number of people who have outlined an area
        threshold = int(0.25*len(set(user_ids)))
        ret,thresh1 = cv2.threshold(aggregate_polygon,threshold,255,cv2.THRESH_BINARY)

        return thresh1

    def __cluster__(self,markings,user_ids,tools,reduced_markings,dimensions,subject_id):
        poly_dictionary = {}

        outlined_area = self.__find_outlined_areas__(user_ids,markings,dimensions)



        # empty_points = np.where(thres1 == 0)
        # plt.imshow(thresh1)
        # plt.show()
        # print(dimensions)

        # now go through on a tool by tool basis
        # this time, the brightness of the polygons corresponds to the tools used
        polygons_by_tools = []


        for poly,t in zip(markings,tools):
            polygons_by_user = [j for j,u in enumerate(user_ids) if u == i]
            # tools_per_user = [tools[j] for j in polygons_by_user]
            polygons_as_arrays = [np.asarray(markings[j],np.int) for j in polygons_by_user]

            template = np.zeros(dimensions,np.uint8)

            # start by drawing the outline of the area
            cv2.polylines(template,polygons_as_arrays,True,255)

            # now take the EXTERNAL contour
            im2, contours, hierarchy = cv2.findContours(template,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            template2 = np.zeros(dimensions,np.uint8)
            # +1 since I don't know if the tools are 1 indexed or 0 indexed
            # if 0-indexed, this might get confused with black - so just playing it safe
            cv2.drawContours(template2,contours,-1,t+1,-1)

            polygons_by_tools.append(template2)

        # find the most common tool used to outline each pixel
        most_common_tool = stats.mode(polygons_by_tools)[0][0]

        clusters = []

        for tool_index in sorted(set(tools)):
            area_by_tool = np.where((most_common_tool==(tool_index+1)) & (thresh1 > 0))

            template = np.zeros(dimensions,np.uint8)
            template[area_by_tool] = 255

            # finally extract each (possible seperate) area which has been outlined by enough people
            # and is of the right tool
            im2, contours, hierarchy = cv2.findContours(template,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                try:
                    clusters.append(self.__new_cluster__(cnt,tool_index,threshold,dimensions))
                except EmptyPolygon:
                    pass

        return clusters,0





    def __new_cluster__(self,polygon,tool_index,threshold,dimensions):
        """
        actually combine everything done so far into the results that we will return
        :return:
        """
        s = polygon.shape
        cluster = {}
        cluster["center"] = polygon.reshape((s[0],s[2])).tolist()
        cluster["area"] = cv2.contourArea(polygon)/(dimensions[0]*dimensions[1])
        if cluster["area"] <= 0.001:
            raise EmptyPolygon()
        # todo - remember why i needed both tool_classification and most_likely_tool
        cluster["tool_classification"] = ({tool_index-1:1},-1)
        cluster["most_likely_tool"] = tool_index
        cluster["users"] = range(threshold)

        return cluster
