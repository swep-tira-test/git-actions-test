#!/bin/bash

# Warning! Special advanced machine learning algorithms incoming!

file=./input.txt

sum=0
while read -r line
do
   (( sum += line ))
done < $file
echo $sum

echo "result=$sum" >> $GITHUB_OUTPUT
