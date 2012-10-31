#!/usr/bin/env python

from math import log
from copy import deepcopy


class Partition(object):

    """
    Class to store clustering information
    """

    score = 0
    concats = []
    partition_vector = None

    def __init__(self, partition_vector):
        """
        self.partitions uses a compound key to retrieve partitions
        key = tuple of (distance_metric, linkage_method, num_classes)
        """
        self.partition_vector = partition_vector

    def __str__(self):
        return str(self.partition_vector)   

    def concatenate_records(self, keys_to_records_map):
        """
        NB: had a version of this which used a reduce construct to concatenate
        the alignments - reduce(lambda x,y: x+y, records_list) - but this led
        to problems of the original object being modified. Deepcopying the 
        first record, ensuring a new memory address for the concatenation, seems 
        more robust.
        """

        memberships = self.get_memberships(self.partition_vector)
        concats = []
        
        index = 1  # index for naming clusters
        for cluster in memberships:
            cluster = sorted(cluster)
            member_records = [keys_to_records_map[n] for n in cluster]
            seed = deepcopy(member_records.pop(0))  # use of deepcopy here is important
            for rec in member_records:
                seed += rec
            seed.name = '-'.join((str(x) for x in cluster))
            concats.append(seed)
        self.concats = concats
        return concats

    def update_score(self, concats_dict):
        self.score = sum([concats_dict[rec.name].tree.score for rec in self.concats])

    def get_memberships(self, partition_vector=None, flatten=False):
            if not partition_vector:
                partition_vector = self.partition_vector

            clusters = list(set(partition_vector))
            result = []
            for c in clusters:
                members = []
                for i in range(len(partition_vector)):
                    if c == partition_vector[i]:
                        members.append(i)
                result.append(set(members))
            result = sorted(result, key=len, reverse=True)
            if flatten:
                flatlist = []
                ext = flatlist.extend
                for cluster in result:
                    ext(list(cluster))
                return flatlist
            return result

    def variation_of_information(self, partition_1, partition_2):
        """ 
        Functions to calculate Variation of Information Metric between two 
        clusterings of the same data - SEE Meila, M. (2007). Comparing 
        clusterings: an information based distance. Journal of Multivariate
        Analysis, 98(5), 873-895. doi:10.1016/j.jmva.2006.11.013 

        dependencies:
        math.log
        
        parameters:
        partition_1 (list / array) - a partitioning of a dataset according to 
                some clustering method. Cluster labels are arbitrary.
        partition_2 (list / array) - another partitioning of the same dataset.
                Labels don't need to match, nor do the number of clusters.

        subfunctions:
        get_memberships - parameter partition (list / array)
            returns a list of length equal to the number of clusters found in
            the partition. Each element is the set of members of the cluster.
            Ordering is arbitrary.

        variables used:
            t = total number of points in the dataset
            m1 = cluster memberships from partition_1
            m2 = cluster memberships from partition_2
            l1 = length (i.e. number of clusters) of m1
            l2 = length of m2
            entropy_1 = Shannon entropy of partition_1
            entropy_2 = Shannon entropy of partition_2
            mut_inf = mutual information of partitions
            prob1 = probability distribution of partition 1 - i.e. the 
                probability that a randomly chosen datapoint belongs to
                each cluster (size of cluster / size of dataset)
            prob2 = as above, for partition 2
            intersect = number of common elements in partition 1 [i] and
                partition 2 [j]
        """

        if len(partition_1) != len(partition_2):
            print 'Partition lists are not the same length'
            return 0
        else:
            total = float(len(partition_1))  # Ensure float division later

        m1 = self.get_memberships(partition_1)
        m2 = self.get_memberships(partition_2)
        l1 = len(m1)
        l2 = len(m2)
        entropy_1 = 0
        entropy_2 = 0
        mut_inf = 0
        for i in range(l1):
            prob1 = len(m1[i]) / total
            entropy_1 -= prob1 * log(prob1, 2)
            for j in range(l2):
                if i == 0:  # only calculate these once
                    prob2 = len(m2[j]) / total
                    entropy_2 -= prob2 * log(prob2, 2)
                intersect = len(m1[i] & m2[j])
                if intersect == 0:
                    continue  # because 0 * log(0) = 0 (lim x->0: xlog(x)->0)
                else:
                    mut_inf += intersect / total * log(total
                            * intersect / (len(m1[i]) * len(m2[j])), 2)

        return entropy_1 + entropy_2 - 2 * mut_inf