#!/bin/bash

file=./input.txt

sum=0
while read -r line
do
   (( sum += line ))
done < $file
echo $sum

echo "::set-output name=result::$(echo $sum)" >> $GITHUB_OUTPUT
