#/bin/bash


# ./runinference.py -d scratch/batch/MSA -t scratch/batch/tr -c scratch/batch/cl -program treecollection -dist rf -l single -s
# rm scratch/batch/tr/cluster* scratch/batch/cl/*

DISTANCES=( euc rf sym geo )
LINKAGES=( single complete ward )

for ((i=0; i<100; i++))
do
    ./runsim.py -d scratch/batch -c 24 -g 5 5 5 5 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 -s 10 -q 
    for j in "${DISTANCES[@]}" 
    do 
        for k in "${LINKAGES[@]}" 
        do
            ./runinference.py -d scratch/batch/MSA -t scratch/batch/tr -c scratch/batch/cl -tmp=./tmp -r ./res4 -program treecollection -dist $j -l $k -q -n 4
            rm scratch/batch/tr/cluster* scratch/batch/cl/*
        done
    done
    rm -r scratch/batch
done

for ((i=0; i<100; i++))
do
    ./runsim.py -d scratch/batch -c 24 -g 5 5 5 5 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 -s 10 -q
    for j in "${DISTANCES[@]}" 
    do 
        for k in "${LINKAGES[@]}" 
        do
            ./runinference.py -d scratch/batch/MSA -t scratch/batch/tr -c scratch/batch/cl -tmp=./tmp -r ./res5 -program treecollection -dist $j -l $k -q -n 5
            rm scratch/batch/tr/cluster* scratch/batch/cl/*
        done
    done
    rm -r scratch/batch
done