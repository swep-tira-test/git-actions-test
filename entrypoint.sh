#!/bin/sh -l

ls -la

file=./input.txt
SUM=0
for num in $(cat $file)
    do
        ((SUM+=num))
done
echo $SUM
echo "summe=$SUM" >> $GITHUB_OUTPUT
