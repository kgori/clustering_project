#!/usr/bin/env python

import dpy_utils


class Tree(object):

    score_regex = re.compile('(?<=Log-likelihood: ).+')

    def __init__(
        self,
        newick=None,
        score=0,
        program=None,
        name=None,
        output=None,
        rooted=None,
        ):

        self.newick = newick
        self.score = score
        self.program = program
        self.name = name
        self.output = output
        self.rooted = self.check_rooted(self.newick)

    def __str__(self):
        """
        Represents the object's information inside
        a newick comment, so is still interpretable
        by a (good) newick parser
        """

        s = '[Tree Object:\n'
        if self.name:
            s += 'Name:\t' + self.name + '\n'
        s += 'Program:\t{0}\n'.format(self.program) \
            + 'Score:\t{0}\n'.format(self.score) \
            + 'Rooted:\t{0}\n'.format(self.rooted) \
            + 'Tree:\t]{0}\n'.format(self.newick)
        return s

    def __eq__(self, other):
        equal = True
        if not self.name == other.name:
            return False
        if not self.newick == other.newick:
            return False
        if not self.program == other.program:
            return False
        if not self.score == other.score:
            return False
        if not self.rooted == other.rooted:
            return False
        if not self.output == other.output:
            return False
        return equal

    def write_to_file(
        self,
        outfile,
        metadata=False,
        suppress_NHX=False,
        ):
        """
        Writes a string representation of the object's contents
        to file.
        """

        writer = open(outfile, 'w')
        if metadata:
            writer.write(str(self))
        else:

            writeable = self.newick
            if suppress_NHX:
                if writeable.startswith('[&R] '):
                    writeable = writeable[5:]
            if not writeable.endswith('\n'):
                writeable += '\n'
            writer.write(writeable)
        writer.close()
        return outfile

    def reroot_newick(self):
        dpy_tree = dpy.Tree.get_from_string(self.newick, 'newick')
        dpy_tree.resolve_polytomies()
        return dpy_tree.as_newick_string() + ';\n'

    def pam2sps(self, multiplier=0.01):
        """
        Scales branch lengths by an order of `multiplier`.
        Default is 0.01, converting PAM units to substitutions
        per site.
        multiplier = 'sps2pam' scales by 100, performing the
        opposite operation.
        multiplier = 'strip' removes branch lengths entirely
        """

        reg_ex = re.compile('(?<=:)[0-9.]+')

        converter = lambda a: str(multiplier * float(a.group()))
        strip_lengths = lambda d: ''

        input_string = self.newick

        if multiplier == 'pam2sps':
            multiplier = 0.01
        elif multiplier == 'sps2pam':
            multiplier = 100

        # Set the output string according to selection

        if multiplier == 'strip':
            output_string = reg_ex.sub(strip_lengths,
                    input_string).replace(':', '')
        else:

            output_string = reg_ex.sub(converter, input_string)

        return Tree(
            output_string,
            self.score,
            self.program,
            self.name,
            self.output,
            self.rooted,
            )

    def extract_gamma_parameter(self):
        gamma_regex = \
            re.compile(r'(?<=Gamma shape parameter: \t\t)[.\d+]+')
        try:
            gamma = float(gamma_regex.search(self.output).group())
        except AttributeError:
            print 'Couldn\'t extract parameters'
            return
        return gamma

    def extract_GTR_parameters(self):
        Afreq_regex = re.compile(r'(?<=f\(A\)= )[.\d+]+')
        Cfreq_regex = re.compile(r'(?<=f\(C\)= )[.\d+]+')
        Gfreq_regex = re.compile(r'(?<=f\(G\)= )[.\d+]+')
        Tfreq_regex = re.compile(r'(?<=f\(T\)= )[.\d+]+')
        AtoC_regex = re.compile(r'(?<=A <-> C    )[.\d+]+')
        AtoG_regex = re.compile(r'(?<=A <-> G    )[.\d+]+')
        AtoT_regex = re.compile(r'(?<=A <-> T    )[.\d+]+')
        CtoG_regex = re.compile(r'(?<=A <-> G    )[.\d+]+')
        CtoT_regex = re.compile(r'(?<=A <-> T    )[.\d+]+')
        GtoT_regex = re.compile(r'(?<=A <-> T    )[.\d+]+')

        try:
            Afreq = float(Afreq_regex.search(self.output).group())
            Cfreq = float(Cfreq_regex.search(self.output).group())
            Gfreq = float(Gfreq_regex.search(self.output).group())
            Tfreq = float(Tfreq_regex.search(self.output).group())
            AtoC = float(AtoC_regex.search(self.output).group())
            AtoG = float(AtoG_regex.search(self.output).group())
            AtoT = float(AtoT_regex.search(self.output).group())
            CtoG = float(CtoG_regex.search(self.output).group())
            CtoT = float(CtoT_regex.search(self.output).group())
            GtoT = float(GtoT_regex.search(self.output).group())
        except AttributeError:
            print 'Couldn\'t extract parameters'
            return

        d = dict(
            Afreq=Afreq,
            Cfreq=Cfreq,
            Gfreq=Gfreq,
            Tfreq=Tfreq,
            AtoC=AtoC,
            AtoG=AtoG,
            AtoT=AtoT,
            CtoG=CtoG,
            CtoT=CtoT,
            GtoT=GtoT,
            )

        return d


    def randomise_branch_lengths(
        self,
        inner_edges,
        leaves,
        distribution_func=np.random.gamma,
        output_format=5,
        ):
        """
        inner_edges and leaves are tuples describing the parameters of the
        distribution function
        distribution_func is a function generating samples from a probability
        distribution (eg gamma, normal ...)
        """

        t = ete2.Tree(self.newick)

        for node in t.iter_descendants():
            if node.children:
                node.dist = max(0, distribution_func(*inner_edges))  # 0 length or greater
            else:
                node.dist = max(0, distribution_func(*leaves))

        t_as_newick = t.write(format=output_format)
        return Tree(t_as_newick, name='random tree')

    def scale(self, scaling_factor):

        return self.pam2sps(scaling_factor)

    @classmethod
    def new_random_yule(cls, nspecies=None, names=None):
        new_tree = cls()
        return new_tree.random_yule(nspecies, names)

    def random_yule(self, nspecies=None, names=None):
        if names and nspecies:
            if not nspecies == len(names):
                nspecies = len(names)
        elif names and not nspecies:
            nspecies = len(names)
        elif not names:
            if not nspecies:
                nspecies = 16
            names = taxonnames.names[:nspecies]
            if nspecies > len(taxonnames.names):
                names.extend(['Sp{0}'.format(i) for i in
                             range(len(taxonnames.names) + 1, nspecies
                             + 1)])

        taxon_set = dpy.TaxonSet(names)
        tree = treesim.uniform_pure_birth(taxon_set)

        newick = '[&R] ' + tree.as_newick_string()
        if not newick.endswith(';'):
            newick += ';'

        return Tree(newick)

    @classmethod
    def new_random_coal(cls, nspecies=None, names=None):
        new_tree = cls()
        return new_tree.random_coal(nspecies, names)

    def random_coal(self, nspecies=None, names=None):
        if names and nspecies:
            if not nspecies == len(names):
                nspecies = len(names)
        elif names and not nspecies:
            nspecies = len(names)
        elif not names:
            if not nspecies:
                nspecies = 16
            names = taxonnames.names[:nspecies]
            if nspecies > len(taxonnames.names):
                names.extend(['Sp{0}'.format(i) for i in
                             range(len(taxonnames.names) + 1, nspecies
                             + 1)])

        taxon_set = dpy.TaxonSet(names)
        tree = treesim.pure_kingman(taxon_set)

        newick = '[&R] ' + tree.as_newick_string()
        if not newick.endswith(';'):
            newick += ';'

        return Tree(newick)

    def get_constrained_gene_tree(
        self,
        scale_to=None,
        population_size=None,
        trim_names=True,
        ):
        """
        Using the current tree object as a species tree, generate
        a gene tree using the constrained Kingman coalescent
        process from dendropy.
        The species tree should probably be a valid, ultrametric
        tree, generated by some pure birth, birth-death or coalescent
        process, but no checks are made.
        Optional kwargs are: 
        -- scale_to, which is a floating point value to
        scale the total tree tip-to-root length to,
        -- population_size, which is a floating point value which 
        all branch lengths will be divided by to convert them to coalescent 
        units, and
        -- trim_names, boolean, defaults to true, trims off the number
        which dendropy appends to the sequence name
        """

        tree = dpy.Tree()
        tree.read_from_string(self.newick, 'newick')

        for leaf in tree.leaf_iter():
            leaf.num_genes = 1

        tree_height = tree.seed_node.distance_from_root() \
            + tree.seed_node.distance_from_tip()

        if scale_to:
            population_size = tree_height / scale_to

        for edge in tree.preorder_edge_iter():
            edge.pop_size = population_size

        gene_tree = treesim.constrained_kingman(tree)[0]

        if trim_names:
            for leaf in gene_tree.leaf_iter():
                leaf.taxon.label = leaf.taxon.label.replace('\'', ''
                        ).split('_')[0]

        newick = '[&R] ' + gene_tree.as_newick_string()
        if not newick.endswith(';'):
            newick += ';'

        return Tree(newick)

    def nni(self):

        # Function to perform a random nearest-neighbour interchange on a tree
        # using Dendropy

        # The dendropy representation of a tree is as if rooted (even when it's
        # not) The node which acts like the root is called the seed node, and this
        # can sit in the middle of an edge which would be a leaf edge in the
        # unrooted tree. NNI moves are only eligible on internal edges, so we
        # need to check if the seed node is sat on a real internal edge, or
        # a fake one.

        # Make a dendropy representation of the tree

        tree = dpy.Tree()
        tree.read_from_string(self.newick, 'newick')
        seed = tree.seed_node
        resolved = False
        if len(seed.child_nodes()) > 2:
            print 'Resolve root trisomy'
            tree.resolve_polytomies()
            resolved = True

        # Make a list of internal edges not including the root edge

        edge_list = list(tree.preorder_edge_iter(lambda edge: \
                         (True if edge.is_internal() and edge.head_node
                         != seed and edge.tail_node
                         != seed else False)))

        # Test whether root edge is eligible (i.e., the edge is not a
        # leaf when the tree is unrooted). If the test passes, add 'root'
        # tp the list of eligible edges

        if not any([x.is_leaf() for x in seed.child_nodes()]):
            edge_list += ['root']

        chosen_edge = random.choice(edge_list)
        print chosen_edge

        # The NNI is done with the chosen edge as root. This will
        # involve rerooting the tree if we choose an edge that isn't
        # the root

        if chosen_edge != 'root':
            tree.reroot_at_edge(chosen_edge, length1=chosen_edge.length
                                / 2, length2=chosen_edge.length / 2,
                                delete_outdegree_one=False)
            root = tree.seed_node
        else:
            root = seed

        # To do the swap: find the nodes on either side of root

        (child_left, child_right) = root.child_nodes()

        # Pick a child node from each of these

        neighbour1 = random.choice(child_left.child_nodes())
        neighbour2 = random.choice(child_right.child_nodes())

        # Prune the chosen nearest neighbours - but don't
        # do any tree structure updates

        tree.prune_subtree(neighbour1, update_splits=False,
                           delete_outdegree_one=False)
        tree.prune_subtree(neighbour2, update_splits=False,
                           delete_outdegree_one=False)

        # Reattach the pruned neighbours to the opposite side
        # of the tree

        child_left.add_child(neighbour2)
        child_right.add_child(neighbour1)

        # Reroot the tree using the original seed node, and
        # update splits

        if not chosen_edge == 'root':
            tree.reroot_at_node(seed, update_splits=True)
        else:
            tree.update_splits()

        if resolved:
            print 'Reinstating root trisomy'
            tree.deroot()

        newick = tree.as_newick_string()
        if not newick.endswith(';'):
            newick += ';'
        if tree.is_rooted:
            newick = '[&R] ' + newick

        return Tree(newick, self.score, self.program, self.name,
                    self.output)

    def spr(self, time=None, disallow_sibling_SPRs=False):

        def _get_blocks(tree, include_leaf_nodes=True):
            dists = []
            blocks = {}
            if include_leaf_nodes:
                iterator = tree.preorder_node_iter()
            else:
                iterator = tree.preorder_internal_node_iter()
            for n in iterator:
                node_height = n.distance_from_root()
                if not n.parent_node:
                    root_height = n.distance_from_root()
                    tree_height = root_height + n.distance_from_tip()
                    parent_height = 0
                else:
                    parent_height = n.parent_node.distance_from_root()
                node_height = round(node_height, 8)
                parent_height = round(parent_height, 8)

                if not node_height in blocks:
                    blocks[node_height] = []

                dists.append((n, parent_height, node_height))

            for time in blocks:
                for (node, parent_h, node_h) in dists:
                    if parent_h < time <= node_h:
                        blocks[time].append(node)

            dists.sort(key=lambda x: x[2])
            return (blocks, dists)

        def _weight_by_branches(blocks):
            intervals = sorted(blocks.keys())
            weighted_intervals = [0] + [None] * (len(intervals) - 1)
            for i in range(1, len(intervals)):
                time_range = intervals[i] - intervals[i - 1]
                num_branches = len(blocks[intervals[i]])
                weighted_range = time_range * num_branches
                weighted_intervals[i] = weighted_range \
                    + weighted_intervals[i - 1]
            return weighted_intervals

        def _get_time(blocks, weights=None):
            d = sorted(blocks.keys())
            if weights:
                samp = random.uniform(weights[0], weights[-1])
                for i in range(len(weights) - 1):
                    if weights[i + 1] >= samp > weights[i]:
                        interval = weights[i + 1] - weights[i]
                        proportion = (samp - weights[i]) / interval
                        break
                drange = d[i + 1] - d[i]
                time = drange * proportion + d[i]
            else:
                time = random.uniform(d[0], d[-1])

            print 'LGT event at time: {0}'.format(time)

            return time

        def _choose_prune_and_regraft_nodes(time, blocks,
                disallow_sibling_SPRs):
            matching_branches = [x for x in dists if x[1] < time < x[2]]

            prune = random.sample(matching_branches, 1)[0]

            if disallow_sibling_SPRs:
                siblings = prune[0].sister_nodes()
                for br in matching_branches:
                    if br[0] in siblings:
                        matching_branches.remove(br)

            matching_branches.remove(prune)

            if matching_branches == []:
                print 'No non-sibling branches available'
                return (None, None)

            regraft = random.sample(matching_branches, 1)[0]

            prune_taxa = [n.taxon.label for n in prune[0].leaf_iter()]
            regraft_taxa = [n.taxon.label for n in
                            regraft[0].leaf_iter()]
            print 'Donor group = {0}'.format(regraft_taxa)
            print 'Receiver group = {0}'.format(prune_taxa)
            return (prune, regraft)

        def _add_node(tree, time, regraft_node):
            parent_node = regraft_node[0].parent_node
            new_node = parent_node.add_child(dpy.Node(),
                    edge_length=time - regraft_node[1])
            tree.reindex_subcomponent_taxa()
            tree.update_splits()
            return new_node

        def _prunef(tree, node):
            tree.prune_subtree(node, update_splits=False,
                               delete_outdegree_one=True)

        def _regraftf(
            tree,
            time,
            target_node,
            child_node,
            ):

            target_node.add_child(child_node[0],
                                  edge_length=child_node[2] - time)
            return tree

        tree = dpy.Tree()
        tree.read_from_string(self.newick, 'newick')
        if self.rooted is None:
            tree.is_rooted = Tree.check_rooted(self.newick)
        else:
            tree.is_rooted = self.rooted
        (blocks, dists) = _get_blocks(tree)
        if not time:
            weights = _weight_by_branches(blocks)
            time = _get_time(blocks, weights)
        (p, r) = _choose_prune_and_regraft_nodes(time, dists,
                disallow_sibling_SPRs=disallow_sibling_SPRs)

        if (p, r) == (None, None):
            return self.spr(disallow_sibling_SPRs=disallow_sibling_SPRs)

        new_node = _add_node(tree, time, r)
        _prunef(tree, p[0])

        _prunef(tree, r[0])

        _regraftf(tree, time, new_node, p)

        _regraftf(tree, time, new_node, r)

        tree.reindex_subcomponent_taxa()
        tree.update_splits()

        newick = tree.as_newick_string()
        if not newick.endswith(';'):
            newick += ';'

        if tree.is_rooted:
            newick = '[&R] ' + newick

        return Tree(newick=newick, rooted=tree.is_rooted)