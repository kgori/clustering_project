#!/usr/bin/env python

import glob
import os
import multiprocessing
import copy
import re
from subprocess import Popen, PIPE, call
from sequence_record import TCSeqRec
from distance_matrix import DistanceMatrix
from clustering import Clustering
from partition import Partition

# from simulation import Simulation

import copy_reg
import types
from random import shuffle
import shutil


def _pickle_method(method):
    """
    Adjust pickling via copy_reg module to make multiprocessing.Pool work
    with class methods (otherwise unpickleable)
    """

    func_name = method.im_func.__name__
    obj = method.im_self
    cls = method.im_class
    if func_name.startswith('__') and not func_name.endswith('__'):

        # deal with mangled names

        cls_name = cls.__name__.lstrip('_')
        func_name = '_%s%s' % (cls_name, func_name)
    return (_unpickle_method, (func_name, obj, cls))


def _unpickle_method(func_name, obj, cls):
    """
    Adjust pickling via copy_reg module to make multiprocessing.Pool work
    with class methods (otherwise unpickleable)
    """

    if obj and func_name in obj.__dict__:
        (cls, obj) = (obj, None)  # if func_name is classmethod
    for cls in cls.__mro__:
        try:
            func = cls.__dict__[func_name]
        except KeyError:
            pass
        else:
            break
    return func.__get__(obj, cls)


copy_reg.pickle(types.MethodType, _pickle_method, _unpickle_method)


class SequenceCollection(object):

    """
    Orchestrating class that should:
    a) work as a central repository for the information generated by the 
       subordinate classes, and
    b) be the only class directly interacted with by the user 

    TO DO:
    implement consistent naming of methods (where appropriate)
    Prefixes:
    get_[something]  - returns the object implied by something
    put_[something]  - puts something in the class data structure
    show_[something] - prints something to screen
    plot_[something] - displays a plot of something
    _[something]     - private method
    """

    def __init__(
        self,
        input_dir=None,
        records=None,
        file_format='fasta',
        datatype='protein',
        helper='./class_files/DV_wrapper.drw',
        gtp_path='./class_files',
        tmpdir='/tmp',
        get_distances=True,
        parallel_load=True,
        overwrite=True,
        ):

        # Unset Variables

        # Store some mappings for data retrieval

        self.records_to_keys = {}
        self.keys_to_records = {}
        self.clusters_to_partitions = {}
        self.partitions = {}
        self.distance_matrices = {}
        self.concats = {}
        self.inferred_trees = {}
        self.Clustering = Clustering()

        # Store some data

        self.files = None
        self.file_format = file_format
        self.datatype = datatype
        self.records = []
        self.length = 0
        self.helper = helper
        self.gtp_path = gtp_path

        # Set Variables

        self.gtp_path = gtp_path
        self.tmpdir = tmpdir

        # Lambda for sorting by name and number

        sort_key = lambda item: tuple((int(num) if num else alpha)
                for (num, alpha) in re.findall(r'(\d+)|(\D+)', item))

        # Can give an input directory as optional argument
        # If given:
        #    read the alignment files
        #    optionally calculate pairwise distances
        #    store the sequence data

        if input_dir:

            files = self.get_files(input_dir, file_format)

            # file checks

            if files == 0:
                print 'There was a problem reading files from {0}'.format(input_dir)
                return

            if get_distances and not os.path.isfile(helper):
                print 'There was a problem finding the darwin helper at {0}'.format(helper)
                return

            # done

            files.sort(key=sort_key)
            self.put_records(files=files, record_list=None,
                             file_format=file_format, datatype=datatype)

                               # takes care of self.length for us

            self.sanitise_records()
            if not os.path.isdir(tmpdir):
                os.mkdir(tmpdir)
        elif records:

        # Can optionally give record objects directly if no input dir specified

            self.put_records(files=None, record_list=records,
                             file_format=file_format, datatype=datatype)

                               # takes care of self.length for us

            self.sanitise_records()

        # Optionally use Darwin to calculate pairwise distances

        if get_distances:
            if parallel_load:
                self.put_dv_matrices_parallel(helper=helper,
                        tmpdir=tmpdir, overwrite=overwrite)
            else:
                self.put_dv_matrices(helper=helper, tmpdir=tmpdir,
                        overwrite=overwrite)

    def __str__(self):
        s = 'SequenceCollection object:\n'
        s += 'Contains {0} alignments\n'.format(self.length)
        return s

    def get_files(self, input_dir, file_format='fasta'):
        """
        Get list of alignment files from an input directory
        *.fa, *.fas and *.phy files only
        Stores in self.files
        """

        if file_format == 'fasta':
            files = glob.glob('{0}/*.fa'.format(input_dir))
            if len(files) == 0:
                files = glob.glob('{0}/*.fas'.format(input_dir))
        elif file_format == 'phylip':
            files = glob.glob('{0}/*.phy'.format(input_dir))
        else:
            print 'Unrecognised file format %s' % file_format
            files = None
        if not files:
            print 'No sequence files found in {0}'.format(input_dir)
            return 0
        return sorted(files)

    def put_records(
        self,
        files=None,
        record_list=None,
        file_format='fasta',
        datatype='protein',
        ):
        """ 
        Reads sequence files from the list generated by
        get_files and stores in self.records
        """

        get_name = lambda i: i[i.rindex('/') + 1:i.rindex('.')]

        if files and not record_list:
            record_list = [TCSeqRec(f, file_format=file_format,
                           name=get_name(f), datatype=datatype)
                           for f in files]
        elif not files and not record_list:

            print 'Can\'t load records - no records or alignment files given'
            return

        enumeration = enumerate(record_list, start=1)
        records_to_keys = dict([(record.name, number) for (number,
                               record) in enumerate(record_list)])
        keys_to_records = dict(enumerate(record_list))
        self.records = record_list
        self.length = len(record_list)
        self.records_to_keys = records_to_keys
        self.keys_to_records = keys_to_records

    def get_records(self):
        """
        Returns list of stored sequence records
        """

        return [self.keys_to_records[i] for i in range(self.length)]

    def sanitise_records(self):
        """
        Sorts records alphabetically, trims whitespace from beginning 
        of record headers, removes '/' characters from headers, 
        replaces spaces with underscores, puts sequences into upper case
        """

        for rec in self.get_records():
            rec.sanitise()

    def put_dv_matrices(
        self,
        tmpdir='/tmp',
        helper='./class_files/DV_wrapper.drw',
        overwrite=True,
        ):

        for rec in self.get_records():
            rec.dv = [rec.get_dv_matrix(tmpdir=tmpdir, helper=helper,
                      overwrite=overwrite)]

    def _unpack_dv(self, packed_args):
        return packed_args[0].get_dv_matrix(*packed_args[1:])

    def _dv_parallel_call(
        self,
        tmpdir='/tmp',
        helper='./class_files/DV_wrapper.drw',
        overwrite=True,
        ):

        nprocesses = min(self.length, multiprocessing.cpu_count() - 1)
        print 'Initialising a pool of {0} processes running {1} jobs...'.format(nprocesses,
                self.length)
        pool = multiprocessing.Pool(nprocesses)
        results = []
        args = []
        names = []
        for rec in self.get_records():
            new_dir = tmpdir + '/' + rec.name
            if not os.path.isdir(new_dir):
                os.mkdir(new_dir)
            args.append((rec, tmpdir + '/' + rec.name, helper,
                        overwrite))
            names.append(rec.name)
        r = pool.map_async(self._unpack_dv, args,
                           callback=results.append)
        r.wait()
        for (w, x, y, z) in args:
            if os.path.isdir(x):
                os.rmdir(x)
        results = results[0]
        print 'Results obtained, closing pool...'
        pool.close()
        pool.join()
        print 'Pool closed'
        return dict(zip(names, results))

    def put_dv_matrices_parallel(
        self,
        tmpdir='/tmp',
        helper='./class_files/DV_wrapper.drw',
        overwrite=True,
        ):

        dv_matrices_dict = self._dv_parallel_call(tmpdir, helper,
                overwrite=overwrite)
        for rec in self.get_records():
            rec.dv = [dv_matrices_dict[rec.name]]

    def get_dv_matrices(self):
        dvs = {}
        for rec in self.get_records():
            dvs[rec.name] = rec.dv
        return dvs

    def _unpack_bionj(self, packed_args):
        return packed_args[0].get_bionj_tree(*packed_args[1:])

    def _bionj_parallel_call(
        self,
        model=None,
        datatype=None,
        rec_list=None,
        ncat=1,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if not rec_list:
            rec_list = self.records
        nprocesses = min(len(rec_list), multiprocessing.cpu_count() - 1)
        print 'Initialising a pool of {0} processes running {1} jobs...'.format(nprocesses,
                len(rec_list))
        pool = multiprocessing.Pool(nprocesses)
        results = []
        args = []
        names = []
        for rec in rec_list:
            args.append((
                rec,
                model,
                datatype,
                ncat,
                tmpdir,
                overwrite,
                ))
            names.append(rec.name)
        r = pool.map_async(self._unpack_bionj, args,
                           callback=results.append)
        r.wait()
        print 'Results obtained, closing pool...'
        pool.close()
        pool.join()
        print 'Pool closed'
        return dict(zip(names, results[0]))

    def _unpack_phyml(self, packed_args):
        return packed_args[0].get_phyml_tree(*packed_args[1:])

    def _phyml_parallel_call(
        self,
        model=None,
        datatype=None,
        rec_list=None,
        ncat=4,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if not rec_list:
            rec_list = self.records
        nprocesses = min(len(rec_list), multiprocessing.cpu_count() - 1)
        print 'Initialising a pool of {0} processes running {1} jobs...'.format(nprocesses,
                len(rec_list))
        pool = multiprocessing.Pool(nprocesses)
        results = []
        args = []
        names = []
        for rec in rec_list:
            args.append((
                rec,
                model,
                datatype,
                ncat,
                tmpdir,
                overwrite,
                ))
            names.append(rec.name)
        r = pool.map_async(self._unpack_phyml, args,
                           callback=results.append)
        r.wait()
        print 'Results obtained, closing pool...'
        pool.close()
        pool.join()
        print 'Pool closed'
        return dict(zip(names, results[0]))

    def _unpack_raxml(self, packed_args):
        return packed_args[0].get_raxml_tree(*packed_args[1:])

    def _raxml_parallel_call(
        self,
        rec_list=None,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if not rec_list:
            rec_list = self.records
        nprocesses = multiprocessing.cpu_count() - 1
        print 'Initialising a pool of {0} processes running {1} jobs...'.format(nprocesses,
                len(rec_list))
        pool = multiprocessing.Pool(nprocesses)
        results = []
        args = []
        names = []
        for rec in rec_list:
            args.append((rec, tmpdir, overwrite))
            names.append(rec.name)
        r = pool.map_async(self._unpack_raxml, args,
                           callback=results.append)
        r.wait()
        pool.close()
        pool.join()
        return dict(zip(names, results[0]))

    def _unpack_TC(self, packed_args):
        return packed_args[0].get_TC_tree(*packed_args[1:])

    def _TC_parallel_call(
        self,
        rec_list=None,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if not rec_list:
            rec_list = self.records
        nprocesses = multiprocessing.cpu_count() - 1
        print 'Initialising a pool of {0} processes running {1} jobs...'.format(nprocesses,
                len(rec_list))
        pool = multiprocessing.Pool(nprocesses)
        results = []
        args = []
        names = []
        for rec in rec_list:
            args.append((rec, tmpdir, overwrite))
            names.append(rec.name)
        r = pool.map_async(self._unpack_TC, args,
                           callback=results.append)
        r.wait()
        pool.close()
        pool.join()
        return dict(zip(names, results[0]))

    def put_trees(
        self,
        rec_list=None,
        program='treecollection',
        model=None,
        datatype=None,
        ncat=4,
        tmpdir=None,
        overwrite=True,
        ):

        if tmpdir is None:
            tmpdir = self.tmpdir
        if not program in ['treecollection', 'raxml', 'phyml', 'bionj']:
            print 'unrecognised program {0}'.format(program)
            return
        if not rec_list:
            rec_list = self.records
        for rec in rec_list:
            if overwrite is False:
                if rec.name in self.inferred_trees:
                    continue
            if program == 'treecollection':
                tree = rec.get_TC_tree(tmpdir=tmpdir,
                        overwrite=overwrite)
            elif program == 'raxml':
                tree = rec.get_raxml_tree(tmpdir=tmpdir,
                        overwrite=overwrite)
            elif program == 'phyml':
                tree = rec.get_phyml_tree(model=model,
                        datatype=datatype, tmpdir=tmpdir, ncat=ncat,
                        overwrite=overwrite)
            elif program == 'bionj':
                tree = rec.get_bionj_tree(model=model,
                        datatype=datatype, tmpdir=tmpdir, ncat=ncat,
                        overwrite=overwrite)
            self.inferred_trees[rec.name] = tree

    def put_trees_parallel(
        self,
        rec_list=None,
        program='treecollection',
        model=None,
        datatype=None,
        ncat=4,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if not program in ['treecollection', 'raxml', 'phyml', 'bionj']:
            print 'unrecognised program {0}'.format(program)
            return
        if not rec_list:
            rec_list = self.records
        if program == 'treecollection':
            trees_dict = self._TC_parallel_call(rec_list=rec_list,
                    tmpdir=tmpdir, overwrite=overwrite)
        elif program == 'raxml':
            trees_dict = self._raxml_parallel_call(rec_list=rec_list,
                    tmpdir=tmpdir, overwrite=overwrite)
        elif program == 'phyml':
            trees_dict = self._phyml_parallel_call(
                rec_list=rec_list,
                model=model,
                datatype=datatype,
                tmpdir=tmpdir,
                ncat=ncat,
                overwrite=overwrite,
                )
        elif program == 'bionj':
            trees_dict = self._bionj_parallel_call(
                rec_list=rec_list,
                model=model,
                datatype=datatype,
                tmpdir=tmpdir,
                ncat=ncat,
                overwrite=overwrite,
                )
        for rec in self.get_records():
            rec.tree = trees_dict[rec.name]
            self.inferred_trees[rec.name] = trees_dict[rec.name]

    def get_trees(self):
        return [rec.tree for rec in self.get_records()]

    def put_distance_matrices(
        self,
        metrics,
        tmpdir='/tmp',
        gtp_path=None,
        normalise=False,
        ):
        """
        Pass this function a list of metrics
        valid kwargs - invert (bool), normalise (bool)
        """

        if not gtp_path:
            gtp_path = self.gtp_path
        if not isinstance(metrics, list):
            metrics = [metrics]
        trees = [rec.tree for rec in self.get_records()]
        for metric in metrics:
            dm = DistanceMatrix(trees, tmpdir=tmpdir, gtp_path=gtp_path)
            dm.get_distance_matrix(metric, normalise=normalise)
            self.distance_matrices[metric] = dm

    def get_distance_matrices(self):
        return self.distance_matrices

    def put_partition(
        self,
        metric,
        cluster_method,
        nclusters,
        prune=True,
        tmpdir=None,
        gtp_path=None,
        recalculate=False,
        ):

        if not tmpdir:
            tmpdir = self.tmpdir
        if not gtp_path:
            gtp_path = self.gtp_path
        if not metric in self.get_distance_matrices():
            self.put_distance_matrices(metric, tmpdir=tmpdir,
                    gtp_path=gtp_path)
        partition_vector = \
            self.Clustering.run_clustering(self.distance_matrices[metric],
                cluster_method, nclusters, prune=prune, recalculate=recalculate)

        self.clusters_to_partitions[(metric, cluster_method,
                                    nclusters)] = partition_vector
        self.partitions[partition_vector] = Partition(partition_vector)
        return partition_vector

    def put_partitions(
        self,
        metrics,
        cluster_methods,
        nclusters,
        prune=True,
        tmpdir=None,
        gtp_path=None,
        recalculate=False,
        ):
        """
        metrics, linkages and nclasses are given as lists, or coerced into 
        lists
        """

        if not isinstance(metrics, list):
            metrics = [metrics]
        if not isinstance(cluster_methods, list):
            cluster_methods = [cluster_methods]
        if not isinstance(nclusters, list):
            nclusters = [nclusters]
        if tmpdir is None:
            tmpdir = self.tmpdir
        if gtp_path is None:
            gtp_path = self.gtp_path
        else:
            nclusters = sorted(nclusters, reverse=True)
        names = [rec.name for rec in self.get_records()]
        for metric in metrics:
            for cluster_method in cluster_methods:
                for n in nclusters:
                    key = (metric, cluster_method, n)
                    if key in self.clusters_to_partitions:
                        continue
                    else:
                        self.put_partition(
                            metric,
                            cluster_method,
                            n,
                            prune=prune,
                            tmpdir=tmpdir,
                            gtp_path=gtp_path,
                            recalculate=recalculate,
                            )

    def concatenate_records(self):
        for p in self.partitions.values():
            p.concatenate_records(self.keys_to_records)
            for concat in p.concats:
                if not concat.name in self.concats:
                    self.concats[concat.name] = concat

    def get_partitions(self):
        pass

    def put_clusters(self):
        pass

    def get_clusters(self):
        pass

    def get_cluster_records(self):
        """
        Returns all concatenated records from cluster analysis
        """

        sort_key = lambda item: tuple((int(num) if num else alpha)
                for (num, alpha) in re.findall(r'(\d+)|(\D+)',
                item.name))
        return sorted(self.concats.values(), key=sort_key)

    def put_cluster_trees(
        self,
        program='treecollection',
        model=None,
        datatype=None,
        ncat=4,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if program not in ['treecollection', 'raxml', 'phyml', 'bionj']:
            print 'unrecognised program {0}'.format(program)
            return
        rec_list = self.get_cluster_records()
        print 'Inferring {0} cluster trees'.format(len(rec_list))
        self.put_trees(
            rec_list=rec_list,
            program=program,
            model=model,
            ncat=ncat,
            datatype=datatype,
            tmpdir=tmpdir,
            overwrite=overwrite,
            )
        self.update_results()

    def update_results(self):
        for partition in self.partitions.values():
            partition.update_score(self.concats)

    def put_cluster_trees_parallel(
        self,
        program='treecollection',
        model=None,
        datatype=None,
        ncat=4,
        tmpdir='/tmp',
        overwrite=True,
        ):

        if program not in ['treecollection', 'raxml', 'phyml', 'bionj']:
            print 'unrecognised program {0}'.format(program)
            return
        rec_list = self.get_cluster_records()
        print 'Inferring {0} cluster trees'.format(len(rec_list))
        if program == 'treecollection':
            cluster_trees_dict = \
                self._TC_parallel_call(rec_list=rec_list,
                    tmpdir=tmpdir, overwrite=overwrite)
        elif program == 'raxml':
            cluster_trees_dict = \
                self._raxml_parallel_call(rec_list=rec_list,
                    tmpdir=tmpdir, overwrite=overwrite)
        elif program == 'phyml':
            cluster_trees_dict = self._phyml_parallel_call(
                rec_list=rec_list,
                model=model,
                datatype=datatype,
                ncat=ncat,
                tmpdir=tmpdir,
                overwrite=overwrite,
                )
        elif program == 'bionj':
            cluster_trees_dict = self._bionj_parallel_call(
                rec_list=rec_list,
                model=model,
                datatype=datatype,
                ncat=ncat,
                tmpdir=tmpdir,
                overwrite=overwrite,
                )
        for rec in rec_list:
            rec.tree = cluster_trees_dict[rec.name]
        self.update_results()

    def get_cluster_trees(self):
        rec_list = sorted(self.get_cluster_records(), key=lambda rec: \
                          rec.name)
        trees = [rec.tree for rec in rec_list]
        return trees

    def get_randomised_alignments(self):

        def pivot(lst):
            new_lst = zip(*lst)
            return [''.join(x) for x in new_lst]

        lengths = [rec.seqlength for rec in self.get_records()]
        datatype = self.records[0].datatype
        concat = copy.deepcopy(self.records[0])
        for rec in self.get_records()[1:]:
            concat += rec
        columns = pivot(concat.sequences)
        shuffle(columns)
        newcols = []
        for l in lengths:
            newcols.append(columns[:l])
            columns = columns[l:]
        newrecs = []
        for col in newcols:
            newseqs = pivot(col)
            newrec = TCSeqRec(headers=concat.headers,
                              sequences=newseqs, datatype=datatype)
            newrecs.append(newrec)
        for i in range(self.length):
            newrecs[i].name = self.records[i].name
        return newrecs

    def make_randomised_copy(self,
                             tmpdir='/tmp',
                             get_distances=True,
                             parallel_load=True,
                             overwrite=True,
                             ):

        shuffled_records = self.get_randomised_alignments()
        randomised_copy = SequenceCollection(
            input_dir=None,
            records=shuffled_records,
            file_format=self.file_format,
            datatype=self.datatype,
            helper=self.helper,
            gtp_path=self.gtp_path,
            tmpdir='/tmp',
            get_distances=get_distances,
            parallel_load=parallel_load,
            overwrite=overwrite,
            )
        return randomised_copy

    def show_memberships(self):

        partitions = self.get_partitions()
        for compound_key in partitions:
            print ' '.join(str(x) for x in compound_key)
            partition = partitions[compound_key]
            print partition
            print self.clustering.get_memberships(partition)

    def plot_dendrogram(
        self,
        metric,
        link,
        nclasses,
        show=True,
        ):

        plot_object = self.clustering.plot_dendrogram((metric, link,
                nclasses))
        if show:
            plot_object.show()
        return plot_object

    def simulate_from_result(
        self,
        compound_key,
        helper='./class_files/DV_wrapper.drw',
        tmpdir='/tmp',
        ):

        shorten = lambda x: '_'.join([str(b)[:5] for b in x])
        result_object = self.get_clusters()[compound_key]
        lengths = [[rec.seqlength for rec in m] for m in
                   result_object.members]
        total_lengths = [sum(x) for x in lengths]
        msa_dir = '{0}/msa'.format(tmpdir)
        if not os.path.isdir(msa_dir):
            os.mkdir(msa_dir)
        k = 1
        for i in range(result_object.length):
            tree = result_object.concats[i].tree
            tree = tree.pam2sps('sps2pam')
            treefile = \
                tree.write_to_file('{0}/{1}_tmptree{2}.nwk'.format(tmpdir,
                                   shorten(compound_key), i))
            outfile = '{0}/{1}_class{2}_params.drw'.format(tmpdir,
                    shorten(compound_key), i)
            length_list = lengths[i]
            total_length = (total_lengths[i] + total_lengths[i] % 3) / 3
            result_object.write_ALF_parameters(
                'alfsim_{0}'.format(i),
                tmpdir,
                'alftmp_{0}'.format(i),
                1,
                total_length,
                treefile,
                outfile,
                )
            os.system('alfsim {0}'.format(outfile))
            record = \
                TCSeqRec(glob.glob('{0}/alftmp_{1}/alfsim_{1}/MSA/*dna.fa'.format(tmpdir,
                         i))[0])

            alf_newick = \
                open('{0}/alftmp_{1}/alfsim_{1}/RealTree.nwk'.format(tmpdir,
                     i)).read()
            replacement_dict = dict(zip(re.findall(r'(\w+)(?=:)',
                                    alf_newick),
                                    re.findall(r'(\w+)(?=:)',
                                    tree.newick)))
            print alf_newick
            print tree.newick
            print replacement_dict
            record.sort_by_name()
            headers = [replacement_dict[x[:x.rindex('/')]] for x in
                       record.headers]
            print headers
            sequences = record.sequences
            print record
            for j in range(len(length_list)):
                start = sum(length_list[:j])
                end = sum(length_list[:j + 1])
                new_sequences = [seq[start:end] for seq in sequences]
                newmsa = TCSeqRec(headers=headers,
                                  sequences=new_sequences,
                                  name='gene{0:0>3}'.format(k))
                k += 1
                newmsa.write_fasta(outfile='{0}/{1}.fas'.format(msa_dir,
                                   newmsa.name))
            shutil.rmtree('{0}/alftmp_{1}'.format(tmpdir, i))
            os.remove(treefile)
            os.remove(outfile)

        new_seqcol_object = SequenceCollection(msa_dir, datatype='dna',
                helper=helper, tmpdir=tmpdir)
        shutil.rmtree('{0}/msa'.format(tmpdir))
        return new_seqcol_object
