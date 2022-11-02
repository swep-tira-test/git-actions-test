#!/bin/sh -l

ls -la

file=./input.txt
SUM=0
while read LINE
do
SUM=expr $SUM + $LINE
done < $file
echo "summe=$SUM" >> $GITHUB_OUTPUT
