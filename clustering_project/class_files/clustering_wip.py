#!/usr/bin/env python

import numpy as np
import os
import dendropy as dpy
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from Bio.Cluster import kmedoids
import matplotlib.pyplot as plt
from matplotlib import cm as CM
from math import log
from copy import copy, deepcopy
from sklearn.cluster import KMeans
from mpl_toolkits.mplot3d import Axes3D
from collections import defaultdict


class Clustering(object):

    """
    Apply clustering methods to distance matrix
    """

    def __init__(self):
        """
        self.partitions uses a compound key to retrieve partitions
        key = tuple of (distance_metric, linkage_method, num_classes)
        """

        pass

    def __str__(self):
        pass

        # s = ''
        # num_partitions = len(self.partitions)
        # num_clusters = len(self.clusters)
        # if num_clusters == 1:
        #     s += '{0} partition calculated:\n'.format(num_partitions)
        # else:
        #     s += '{0} partitions calculated:\n'.format(num_partitions)
        # for p in self.partitions:
        #     s += ' '.join(str(x) for x in p) + '\n'
        # return s


    def run_kmedoids(self, dm, nclusters):

        if dm.metric == 'rf':
            matrix = dm.add_noise(dm.matrix)
        else:
            matrix = dm.matrix

        p = [kmedoids(matrix, nclusters=nclusters, npass=100) for _ in
             range(100)]
        p.sort(key=lambda x: x[1])
        T = self.order(p[0][0])
        return T

    def run_spectral(
        self,
        dm,
        nclusters,
        prune=True,
        ):

        if dm.metric == 'rf':
            matrix = dm.add_noise(dm.matrix)
        else:
            matrix = dm.matrix

        laplacian = self.spectral(matrix, prune=prune)
        (eigvals, eigvecs, cve) = self.get_eigen(laplacian,
                standardize=False)
        coords = self.get_coords_by_dimension(eigvals, eigvecs, cve,
                nclusters, normalise=True)[0]
        est = KMeans(n_clusters=nclusters)
        est.fit(coords)
        T = self.order(est.labels_)
        return T

    def run_hierarchical(
        self,
        dm,
        nclusters,
        linkage_method,
        ):

        if dm.metric == 'rf':
            matrix = dm.add_noise(dm.matrix)
        else:
            matrix = dm.matrix

        linkmat = linkage(matrix, linkage_method)
        linkmat_size = len(linkmat)
        if nclusters <= 1:
            br_top = linkmat[linkmat_size - nclusters][2]
        else:
            br_top = linkmat[linkmat_size - nclusters + 1][2]
        if nclusters >= len(linkmat):
            br_bottom = 0
        else:
            br_bottom = linkmat[linkmat_size - nclusters][2]
        threshold = 0.5 * (br_top + br_bottom)
        T = fcluster(linkmat, threshold, criterion='distance')
        T = self.order(T)
        return T

    def run_MDS(self, dm, nclusters):

        if dm.metric == 'rf':
            matrix = dm.add_noise(dm.matrix)
        else:
            matrix = dm.matrix

        dbc = self.get_double_centre(matrix)
        (eigvals, eigvecs, cve) = self.get_eigen(dbc, standardize=True)
        coords = self.get_coords_by_cutoff(eigvals, eigvecs, cve, 95,
                normalise=False)
        est = KMeans(n_clusters=nclusters)
        est.fit(coords)
        T = self.order(est.labels_)
        return T

    def order(self, l):
        """
        The clustering returned by the hcluster module gives 
        group membership without regard for numerical order 
        This function preserves the group membership, but sorts 
        the labelling into numerical order
        """

        list_length = len(l)

        d = defaultdict(list)
        for (i, element) in enumerate(l):
            d[element].append(i)

        l2 = [None] * list_length

        for (name, index_list) in enumerate(sorted(d.values(),
                key=min), start=1):
            for index in index_list:
                l2[index] = name

        return l2

    def plot_embedding(
        self,
        metric,
        linkage,
        nclasses,
        dimensions=3,
        embed='MDS',
        standardize=False,
        normalise=True,
        ):

        if not dimensions in [2, 3]:
            print '2D or 3D only'
            return

        dm = self.distance_matrices[metric]
        partition = self.partitions[(metric, linkage, nclasses)]

        if embed == 'MDS':
            dbc = self.get_double_centre(dm)
            (eigvals, eigvecs, cve) = self.get_eigen(dbc,
                    standardize=standardize)
            (coords, varexp) = self.get_coords_by_dimension(eigvals,
                    eigvecs, cve, dimensions, normalise=normalise)
        elif embed == 'spectral':

            laplacian = self.spectral(dm)
            (eigvals, eigvecs, cve) = self.get_eigen(laplacian,
                    standardize=standardize)
            (coords, varexp) = self.get_coords_by_dimension(eigvals,
                    eigvecs, cve, dimensions, normalise=normalise)
        else:

            print 'Embedding must be one of MDS or spectral (default=MDS)'
            return

        colors = 'bgrcmyk'
        fig = plt.figure()
        if dimensions == 3:
            ax = fig.add_subplot(111, projection='3d')
        else:
            ax = fig.add_subplot(111)
        for i in range(len(partition)):
            ax.scatter(color=colors[partition[i] % len(colors)],
                       *coords[i])
        return fig

    def plot_dendrogram(self, compound_key):
        """
        Extracts data from clustering to plot dendrogram
        """

        partition = self.partitions[compound_key]
        (linkmat, names, threshold) = self.plotting_info[compound_key]
        fig = plt.figure(figsize=(11.7, 8.3))
        dendrogram(
            linkmat,
            color_threshold=threshold,
            leaf_font_size=8,
            leaf_rotation=90,
            leaf_label_func=lambda leaf: names[leaf] + '_' \
                + str(partition[leaf]),
            count_sort=True,
            )
        plt.suptitle('Dendrogram', fontsize=16)
        plt.title('Distance metric: {0}    Linkage method: {1}    Number of classes: {2}'.format(compound_key[0],
                  compound_key[1], compound_key[2]), fontsize=12)
        plt.axhline(threshold, color='grey', ls='dashed')
        plt.xlabel('Gene')
        plt.ylabel('Distance')
        return fig

    # ## Methods for multidimensional scaling

    def get_double_centre(self, matrix):
        """ 
        Double-centres (Gower centres) the input matrix as follows:
        square the input matrix and divide by -2
        from each element subtract the row and column means,
            and add the overall mean
        Returns the double-centred matrix
        """

        matrix = copy(matrix)
        matrix *= matrix
        matrix /= -2.0
        size = len(matrix)
        output = np.zeros([size, size])
        row_means = np.array([np.mean(row) for row in matrix])
        col_means = np.array([np.mean(col) for col in matrix.T])
        col_means.shape = (size, 1)
        matrix_mean = np.mean(matrix)
        matrix -= row_means
        matrix -= col_means
        matrix += matrix_mean
        return matrix

    def get_eigen(self, matrix, standardize=False):
        """
        Calculates the eigenvalues and eigenvectors from the double-
        centred matrix
        Returns a tuple of (eigenvalues, eigenvectors, cumulative
        percentage of variance explained)
        eigenvalues and eigenvectors are sorted in order of eigenvalue
        magnitude, high to low 
        """

        (vals, vecs) = np.linalg.eigh(matrix)
        ind = vals.argsort()[::-1]
        vals = vals[ind]
        vecs = vecs[:, ind]
        cum_var_exp = np.cumsum(100 * abs(vals) / sum(abs(vals)))
        if standardize:
            vecs = vecs * np.sqrt(abs(vals))
        return (vals, vecs, cum_var_exp)

    def get_coords_by_cutoff(
        self,
        vals,
        vecs,
        cum_var_exp,
        cutoff=95,
        normalise=True,
        ):
        """
        Returns fitted coordinates in as many dimensions as are
        needed to explain a given amount of variance (specified 
        in the cutoff)
        """

        i = np.where(cum_var_exp >= cutoff)[0][0]
        coords_matrix = vecs[:, :i + 1]

        if normalise:
            coords_matrix = self.normalise_coords(coords_matrix)
        return coords_matrix

    def get_coords_by_dimension(
        self,
        vals,
        vecs,
        cum_var_exp,
        dimensions=3,
        normalise=True,
        ):
        """
        Returns fitted coordinates in specified number of dimensions,
        and the amount of variance explained)
        """

        coords_matrix = vecs[:, :dimensions]
        varexp = cum_var_exp[dimensions - 1]
        if normalise:
            coords_matrix = self.normalise_coords(coords_matrix)
        return (coords_matrix, varexp)

    def normalise_coords(self, coords_matrix):
        sqsum = np.sum(coords_matrix ** 2,
                       axis=1).reshape(coords_matrix.shape[0], -1)
        return coords_matrix / np.sqrt(sqsum)

    def spectral(
        self,
        distance_matrix,
        prune=True,
        sigma7=False,
        ):
        """
        1st: Calculates an affinity matrix from a distance matrix, using the
        local scaling transform from Zelnik-Manor and Perona (2004):
        affinity[i,j] = exp(-distance[i,j]^2/(sigma_i*sigma_j)).
        2nd: Returns a normalised Laplacian matrix from the affinity matrix.
        Optionally the similarity matrix can be pruned using a k-nearest neighbours
        approach as in Leigh et al. (2011).
        Note: the normalised Laplacian according to Ng et al. is different to the
        normalised Laplacian according to Von Luxburg: 
        Ng et al. give D(-1/2). W. D(-1/2)
        VL gives I - D(-1/2). W. D(-1/2)

        References: 
        Luxburg, U. (2007). A tutorial on spectral clustering. 
        Statistics and Computing, 17(4), 395-416. 
        doi:10.1007/s11222-007-9033-z

        Leigh, J. W. et al. (2011). 
        Let Them Fall Where They May: Congruence Analysis in Massive 
        Phylogenetically Messy Data Sets. 
        Molecular Biology and Evolution, 28(10), 2773-2785.
        doi:10.1093/molbev/msr110

        P Perona and L. Zelnik-Manor. (2004).
        Self-tuning spectral clustering.
        Advances in neural information processing systems, 2004 vol. 17 pp. 1601-1608
        """

        size = len(distance_matrix)  # assume square and symmetrical input

        def isconnected(matrix):
            """
            Checks that all nodes are reachable from the first node - i.e. that
            the graph is fully connected. The approach is borrowed from 
            isconnected function from graph.c in Leigh's Conclustador program.
            """

            # INIT

            matrix = np.array(matrix)
            num_nodes = len(matrix)
            checklist = [0]
            checklength = 1
            reachable = [0]

            # ALGORITHM

            while checklength > 0:
                node = checklist.pop(0)
                checklength -= 1
                for edge in range(num_nodes):
                    if matrix[node, edge] == 1:
                        reachable_node = edge
                        if reachable_node not in reachable:
                            reachable.append(reachable_node)
                            checklist.append(reachable_node)
                            checklength += 1

            # RESULT

            for i in range(num_nodes):
                if not i in reachable:
                    return False
            return True

        def nodivzero(d):
            if 0 in d.values():
                return False
            else:
                return True

        def knn(matrix, k):
            """
            Acts on distance matrix. For each datapoint, finds
            the `k` nearest neighbours. Returns an adjacency
            matrix, and a dictionary of the kth distance for 
            each node.
            """

            kneighbour_matrix = np.zeros([size, size])
            max_dists = {}
            for i in range(size):
                sorted_dists = matrix[i].argsort()
                for j in sorted_dists[:k]:
                    kneighbour_matrix[i, j] = kneighbour_matrix[j, i] = \
                        1
                    max_dists[i] = matrix[i, sorted_dists[k - 1]]
            return (kneighbour_matrix, max_dists)

        def get_affinity_matrix(distance_matrix, kneighbour_matrix,
                                max_dists):
            """
            Makes weighted adjacency matrix along the lines of
            Zelnik-Manor and Perona (2004), with local scaling.
            """

            affinity_matrix = np.zeros([size, size])
            for i in range(size):
                for j in range(size):
                    if i != j and kneighbour_matrix[i, j] == 1:
                        distance = distance_matrix[i, j]
                        sigma_i = max_dists[i]
                        sigma_j = max_dists[j]
                        affinity_matrix[i, j] = np.exp(-distance ** 2
                                / (sigma_i * sigma_j))
            return affinity_matrix

        def laplace(affinity_matrix):

            D = np.diag(affinity_matrix.sum(axis=1))
            invRootD = np.sqrt(np.linalg.inv(D))
            return np.dot(np.dot(invRootD, affinity_matrix), invRootD)

        # prune graph edges, but require graph be fully connected
        if prune:  # 'guess a number' strategy
            mink = 1
            maxk = size
            guessk = int(np.log(size).round())
            while maxk - mink != 1:
                test = knn(distance_matrix, guessk)
                if isconnected(test[0]) and nodivzero(test[1]):

                    # either correct or too high
                    # try a lower number

                    maxk = guessk
                    guessk = mink + (guessk - mink) / 2
                else:

                    # too low

                    mink = guessk
                    guessk = guessk + (maxk - guessk) / 2
            (kneighbour_matrix, max_dists) = knn(distance_matrix,
                    guessk + 1)
        else:

            (kneighbour_matrix, max_dists) = knn(distance_matrix, size)

        affinity_matrix = get_affinity_matrix(distance_matrix,
                kneighbour_matrix, max_dists)
        md7 = knn(distance_matrix, 7)[1]
        if nodivzero(md7):
            am7 = get_affinity_matrix(distance_matrix,
                    kneighbour_matrix, md7)
        else:
            print 'Setting sigma(i) > d(S(i),S(7)) to avoid dividing by zero.'
            if prune:
                print 'Sigma = d(S(i),S({0})'.format(guessk + 1)
            else:
                print 'Sigma = d(S(i),S({0})'.format(size)
            sigma7 = False

        if sigma7:
            return laplace(am7)
        else:
            return laplace(affinity_matrix)
