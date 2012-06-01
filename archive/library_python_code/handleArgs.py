#!/usr/bin/env python

import sys

def handleArgs(argv,help="no arguments given\n"):
    """ argv = sys.argv, i.e a list of commandline arguments, 
        with -a -b type flags
        It returns a dictionary in which flags are keys and their following arguments
        are values. If a flag is not followed by a value the dictionary stores 'None'
        Flags can be given in any order, and repetition overwrites
    """
    if len(argv) < 2: 
        print help
        sys.exit()
            
    argv = argv[1:]
    flagDic = {}
    for i in range(len(argv)):
        if argv[i].startswith("-"):
            try: 
                if not argv[i+1].startswith("-"): 
                    flagDic[argv[i]] = argv[i+1]
                else: flagDic[argv[i]] = None
            except IndexError: flagDic[argv[i]] = None
    return flagDic

